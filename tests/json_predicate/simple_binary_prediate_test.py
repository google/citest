# Copyright 2015 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=too-many-arguments
# pylint: disable=too-many-public-methods

import unittest

from citest.base import (
    ExecutionContext,
    JsonSnapshotHelper)
from citest.json_predicate import PathValue
import citest.json_predicate as jp


class JsonSimpleBinaryPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    try:
      JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)
    except AssertionError:
      print '\nEXPECT\n{0!r}\n\nGOT\n{1!r}\n'.format(expect, have)
      raise

  def assertGood(self, expect_value, pred, context=None):
    """Assert that got_result is expect_value returned by pred as valid."""
    path_value = PathValue('', expect_value)
    got_result = pred(context or ExecutionContext(), expect_value)
    expect = jp.PathValueResult(pred=pred, source=expect_value, target_path='',
                                path_value=path_value, valid=True)
    self.assertEqual(expect, got_result)

  def assertBad(self, expect_value, pred, context=None):
    """Assert that got_result is expect_value returned by pred as invalid."""
    path_value = PathValue('', expect_value)
    got_result = pred(context or ExecutionContext(), expect_value)
    expect = jp.PathValueResult(pred=pred, source=expect_value, target_path='',
                                path_value=path_value, valid=False)
    self.assertEqual(expect, got_result)

  def test_string_eq(self):
    eq_abc = jp.STR_EQ('abc')
    self.assertGood('abc', eq_abc)
    self.assertBad('abcd', eq_abc)

  def test_string_ne(self):
    ne_abc = jp.STR_NE('abc')
    self.assertGood('abcd', ne_abc)
    self.assertBad('abc', ne_abc)

  def test_indirect_string(self):
    context = ExecutionContext(TEST='abc')
    eq_abc = jp.STR_EQ(lambda x: x['TEST'])
    self.assertGood('abc', eq_abc, context=context)
    self.assertBad('abcd', eq_abc, context=context)

  def test_factory_type_ok(self):
    context = ExecutionContext()
    factory = jp.SimpleBinaryPredicateFactory(
        '==', lambda a, b: True, operand_type=basestring)

    pred = factory('is a string')
    self.assertTrue(pred(context, 'ok'))

    pred = factory(lambda x: 'is a string')
    self.assertTrue(pred(context, 'ok'))

  def test_factory_type_mismatch(self):
    context = ExecutionContext()
    factory = jp.SimpleBinaryPredicateFactory(
        '==', lambda a, b: True, operand_type=basestring)
    self.assertRaises(TypeError, factory, ['not a string'])

    pred = factory(lambda x: ['not a string'])
    self.assertRaises(TypeError, pred, context, 'ok')

  def test_string_substr(self):
    substr_q = jp.STR_SUBSTR('q')
    substr_pqr = jp.STR_SUBSTR('pqr')
    self.assertGood('pqr', substr_q)
    self.assertGood('rqp', substr_q)
    self.assertGood('pqr', substr_pqr)
    self.assertBad('abc', substr_q)
    self.assertBad('xyz', substr_q)

  def simple_operand_type_mismatch_helper(self,
                                            context, expected_type, factory,
                                            good_operand, bad_operand):
    """Helper method used to generate operand type mismatch errors.

    Args:
      factory: The factory to test.
      good_operand: A good operand value.
      bad_operand: A bad operand value.
    """
    self.assertRaises(TypeError, factory, bad_operand)

    pred = factory(good_operand)
    try:
      self.assertEqual(
          jp.TypeMismatchError(
              expected_type, bad_operand.__class__, bad_operand),
          pred(context, bad_operand))
    except:
      print '\nFAILED value={0} pred={1}'.format(good_operand, pred.name)
      raise

  def test_simple_string_operator_type_mismatch(self):
    context = ExecutionContext()
    for value in [['value'], {'a':'A'}, 1]:
      for factory in [jp.STR_EQ, jp.STR_NE]:
        self.simple_operand_type_mismatch_helper(
            context, basestring, factory,
            good_operand='test value', bad_operand=value)

  def test_string_specific_operator_type_mismatch(self):
    context = ExecutionContext()
    operand = 'valid string operand.'
    for value in [['value'], {'a':'A'}, 1]:
      for factory in [jp.STR_SUBSTR]:
        self.simple_operand_type_mismatch_helper(
            context, basestring, factory, operand, value)

  def test_dict_eq(self):
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': 'A', 'b': 'B'}
    eq_pred = jp.DICT_EQ(operand)

    self.assertBad(letters, eq_pred)
    self.assertGood(operand, eq_pred)
    self.assertBad({'a': 'A'}, eq_pred)

  def test_dict_eq_indirect(self):
    context = ExecutionContext(testA='A', testKey='b')
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': lambda x: x['testA'], 'b': 'B'}
    actual_operand = {'a': 'A', 'b': 'B'}
    eq_pred = jp.DICT_EQ(operand)

    self.assertBad(letters, eq_pred, context=context)
    self.assertGood(actual_operand, eq_pred, context=context)
    self.assertBad({'a': 'A'}, eq_pred, context=context)

  def test_dict_ne(self):
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': 'A', 'b': 'B'}
    ne_pred = jp.DICT_NE(operand)

    self.assertGood(letters, ne_pred)
    self.assertBad(operand, ne_pred)
    self.assertGood({'a': 'A'}, ne_pred)

  def test_simple_dict_operator_type_mismatch(self):
    context = ExecutionContext()
    operand = {'a': 'A'}
    for value in [['a'], 'a', 1]:
      for factory in [jp.DICT_EQ, jp.DICT_NE]:
        self.simple_operand_type_mismatch_helper(
            context, dict, factory, good_operand=operand, bad_operand=value)

  def test_dict_specific_operator_type_mismatch(self):
    context = ExecutionContext()
    operand = {'a': 'A'}
    for value in [['a'], 'a', 1]:
      for factory in [jp.DICT_SUBSET]:
        self.simple_operand_type_mismatch_helper(
            context, dict, factory, operand, value)


if __name__ == '__main__':
  unittest.main()
