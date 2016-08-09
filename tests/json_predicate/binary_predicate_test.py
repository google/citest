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


def good_result(path_value, pred, source=None, target_path=''):
  """Constructs a JsonFoundValueResult where pred returns value as valid."""
  source = path_value.value if source is None else source
  return jp.PathValueResult(pred=pred, source=source, target_path=target_path,
                            path_value=path_value, valid=True)


def bad_result(path_value, pred, source=None, target_path=''):
  """Constructs a JsonFoundValueResult where pred returns value as invalid."""
  source = path_value.value if source is None else source
  return jp.PathValueResult(pred=pred, source=source, target_path=target_path,
                            path_value=path_value, valid=False)


class JsonBinaryPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    try:
      JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)
    except AssertionError:
      print '\nEXPECT\n{0!r}\n\nGOT\n{1!r}\n'.format(expect, have)
      raise

  def assertGoodResult(self, expect_value, pred, got_result,
                       source=None, target_path=''):
    """Assert that got_result is expect_value returned by pred as valid."""
    self.assertEqual(good_result(expect_value, pred,
                                 source=source, target_path=target_path),
                     got_result)

  def assertBadResult(self, expect_value, pred, got_result,
                      source=None, target_path=''):
    """Assert that got_result is expect_value returned by pred as invalid."""
    self.assertEqual(bad_result(expect_value, pred,
                                source=source, target_path=target_path),
                     got_result)

  def test_string_eq(self):
    context = ExecutionContext()
    eq_abc = jp.STR_EQ('abc')
    self.assertGoodResult(PathValue('', 'abc'), eq_abc, eq_abc(context, 'abc'))
    self.assertBadResult(PathValue('', 'abcd'), eq_abc, eq_abc(context, 'abcd'))

  def test_string_ne(self):
    context = ExecutionContext()
    ne_abc = jp.STR_NE('abc')
    self.assertGoodResult(PathValue('', 'abcd'),
                          ne_abc, ne_abc(context, 'abcd'))
    self.assertBadResult(PathValue('', 'abc'),
                         ne_abc, ne_abc(context, 'abc'))

  def test_indirect_string(self):
    context = ExecutionContext(TEST='abc')
    eq_abc = jp.STR_EQ(lambda x: x['TEST'])
    self.assertGoodResult(PathValue('', 'abc'), eq_abc, eq_abc(context, 'abc'))
    self.assertBadResult(PathValue('', 'abcd'), eq_abc, eq_abc(context, 'abcd'))

  def test_factory_type_ok(self):
    context = ExecutionContext()
    factory = jp.StandardBinaryPredicateFactory(
        '==', lambda a, b: True, operand_type=basestring)

    pred = factory('is a string')
    self.assertTrue(pred(context, 'ok'))

    pred = factory(lambda x: 'is a string')
    self.assertTrue(pred(context, 'ok'))

  def test_factory_type_mismatch(self):
    context = ExecutionContext()
    factory = jp.StandardBinaryPredicateFactory(
        '==', lambda a, b: True, operand_type=basestring)
    self.assertRaises(TypeError, factory, ['not a string'])

    pred = factory(lambda x: ['not a string'])
    self.assertRaises(TypeError, pred, context, 'ok')

  def test_string_substr(self):
    context = ExecutionContext()
    substr_q = jp.STR_SUBSTR('q')
    substr_pqr = jp.STR_SUBSTR('pqr')
    self.assertGoodResult(PathValue('', 'pqr'),
                          substr_q, substr_q(context, 'pqr'))
    self.assertGoodResult(PathValue('', 'rqp'),
                          substr_q, substr_q(context, 'rqp'))
    self.assertGoodResult(PathValue('', 'pqr'),
                          substr_pqr, substr_pqr(context, 'pqr'))
    self.assertBadResult(PathValue('', 'abc'),
                         substr_q, substr_q(context, 'abc'))
    self.assertBadResult(PathValue('', 'xyz'),
                         substr_q, substr_q(context, 'xyz'))

  def standard_operand_type_mismatch_helper(self,
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

  def test_standard_string_operator_type_mismatch(self):
    context = ExecutionContext()
    for value in [['value'], {'a':'A'}, 1]:
      for factory in [jp.STR_EQ, jp.STR_NE]:
        self.standard_operand_type_mismatch_helper(
            context, basestring, factory,
            good_operand='test value', bad_operand=value)

  def test_string_specific_operator_type_mismatch(self):
    context = ExecutionContext()
    operand = 'valid string operand.'
    for value in [['value'], {'a':'A'}, 1]:
      for factory in [jp.STR_SUBSTR]:
        self.standard_operand_type_mismatch_helper(
            context, basestring, factory, operand, value)

  def test_dict_eq(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': 'A', 'b': 'B'}
    eq_pred = jp.DICT_EQ(operand)

    self.assertBadResult(PathValue('', letters),
                         eq_pred, eq_pred(context, letters))
    self.assertGoodResult(PathValue('', operand),
                          eq_pred, eq_pred(context, operand))
    self.assertBadResult(PathValue('', {'a': 'A'}),
                         eq_pred, eq_pred(context, {'a': 'A'}))

  def test_dict_eq_indirect(self):
    context = ExecutionContext(testA='A', testKey='b')
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': lambda x: x['testA'], 'b': 'B'}
    actual_operand = {'a': 'A', 'b': 'B'}
    eq_pred = jp.DICT_EQ(operand)

    self.assertBadResult(PathValue('', letters),
                         eq_pred, eq_pred(context, letters))
    self.assertGoodResult(PathValue('', actual_operand),
                          eq_pred, eq_pred(context, actual_operand))
    self.assertBadResult(PathValue('', {'a': 'A'}),
                         eq_pred, eq_pred(context, {'a': 'A'}))

  def test_dict_ne(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': 'A', 'b': 'B'}
    ne_pred = jp.DICT_NE(operand)

    self.assertGoodResult(PathValue('', letters),
                          ne_pred, ne_pred(context, letters))
    self.assertBadResult(PathValue('', operand),
                         ne_pred, ne_pred(context, operand))
    self.assertGoodResult(PathValue('', {'a': 'A'}),
                          ne_pred, ne_pred(context, {'a': 'A'}))

  def test_dict_simple_subset(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    operand = {'a': 'A', 'b': 'B'}
    subset_pred = jp.DICT_SUBSET(operand)

    self.assertGoodResult(PathValue('', letters),
                          subset_pred, subset_pred(context, letters))
    self.assertGoodResult(PathValue('', operand),
                          subset_pred, subset_pred(context, operand))
    source = {'a':'A'}
    self.assertEqual(
        jp.MissingPathError(source=source, target_path='b',
                            path_value=PathValue('', source)),
        subset_pred(context, source))

  def test_dict_nested_subset(self):
    context = ExecutionContext()
    small = {'first':'Apple', 'second':'Banana'}
    small_subset_pred = jp.DICT_SUBSET(small)

    big = {'first':'Apple', 'second':'Banana', 'third':'Cherry'}

    self.assertGoodResult(
        PathValue('', big), small_subset_pred, small_subset_pred(context, big))

    small_nested = {'outer':small}
    small_nested_subset_pred = jp.DICT_SUBSET(small_nested)

    big_nested = {'outer':big, 'another':big}
    self.assertGoodResult(PathValue('', big_nested),
                          small_nested_subset_pred,
                          small_nested_subset_pred(context, big_nested))

  def test_dict_nested_subset_exact_keys(self):
    context = ExecutionContext()
    small_dict = {'first':'Apple', 'second':'Banana'}
    small_nested_dict = {'outer':small_dict}

    # In dictionary we want exact key matches, not subkeys.
    operand = {'out':{'first':'Apple'}}
    subset_pred = jp.DICT_SUBSET(operand)
    self.assertEqual(
        jp.MissingPathError(source=small_nested_dict, target_path='out',
                            path_value=PathValue('', small_nested_dict)),
        subset_pred(context, small_nested_dict))

    # In dictionary we want exact key matches, not subkeys.
    nested_operand = {'fir':'Apple'}
    operand = {'outer':nested_operand}
    subset_pred = jp.DICT_SUBSET(operand)
    self.assertEqual(
        jp.MissingPathError(source=small_nested_dict,
                            target_path=jp.PATH_SEP.join(['outer', 'fir']),
                            path_value=PathValue('outer', small_dict)),
        subset_pred(context, small_nested_dict))

  def test_dict_nested_subset_exact_values(self):
    context = ExecutionContext()
    small = {'first':'Apple', 'second':'Banana'}
    small_nested = {'outer':small}

    # In dictionary we want exact matches of strings, not substrings.
    nested_operand = {'first':'A'}
    operand = {'outer':nested_operand}
    subset_pred = jp.DICT_SUBSET(operand)

    self.assertEqual(
        jp.PathValueResult(
            valid=False, pred=jp.STR_EQ('A'),
            path_value=PathValue(jp.PATH_SEP.join(['outer', 'first']), 'Apple'),
            source=small_nested,
            target_path=jp.PATH_SEP.join(['outer', 'first'])),
        subset_pred(context, small_nested))

  def test_dict_subset_with_array_values_ok(self):
    context = ExecutionContext()
    small = {'a':['A'], 'b':[1, 2]}
    big = {'a':['A', 'B', 'C'], 'b':[1, 2, 3], 'c':['red', 'yellow']}
    small_nested = {'first':small}
    big_nested = {'first':big, 'second':big}

    small_subset_pred = jp.DICT_SUBSET(small)
    nested_subset_pred = jp.DICT_SUBSET(small_nested)

    # These are matching the outer source objects because they contain
    # the subset we are looking for.
    self.assertGoodResult(
        PathValue('', big), small_subset_pred, small_subset_pred(context, big))
    self.assertGoodResult(
        PathValue('', big_nested), nested_subset_pred,
        nested_subset_pred(context, big_nested))

  def test_dict_subset_with_array_values_bad(self):
    context = ExecutionContext()
    small = {'a':['A'], 'b':[1, 2]}
    big = {'a':['A', 'B', 'C'], 'b':[1, 2]}
    small_nested = {'first':small}
    big_nested = {'first':big, 'second':big}

    big_subset_pred = jp.DICT_SUBSET(big)
    nested_subset_pred = jp.DICT_SUBSET(big_nested)
    list_subset_pred = jp.LIST_SUBSET(big['a'])

    self.assertBadResult(
        expect_value=PathValue('a', small['a']),
        pred=list_subset_pred,
        got_result=big_subset_pred(context, small),
        source=small, target_path='a')

  def test_standard_dict_operator_type_mismatch(self):
    context = ExecutionContext()
    operand = {'a': 'A'}
    for value in [['a'], 'a', 1]:
      for factory in [jp.DICT_EQ, jp.DICT_NE]:
        self.standard_operand_type_mismatch_helper(
            context, dict, factory, good_operand=operand, bad_operand=value)

  def test_dict_specific_operator_type_mismatch(self):
    context = ExecutionContext()
    operand = {'a': 'A'}
    for value in [['a'], 'a', 1]:
      for factory in [jp.DICT_SUBSET]:
        self.standard_operand_type_mismatch_helper(
            context, dict, factory, operand, value)

  def test_dict_subset_with_array_nodes(self):
    # See test_collect_with_dict_subset for comparison.
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2}
    both = [letters, numbers]
    source = {'items': both}

    # This doesnt traverse through the list because we are looking for
    # a dictionary subset. We were expecting a dict with an 'a' but we
    # found only a dict with 'items'.
    letter_subset_pred = jp.DICT_SUBSET({'a':'A'})
    self.assertEqual(
        jp.MissingPathError(source=source, target_path='a',
                            path_value=PathValue('', source)),
        letter_subset_pred(context, source))

  def test_collect_with_dict_subset(self):
    # See test_dict_subset_with_array_nodes for comparision.
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2}
    both = [letters, numbers]
    source = {'items': both}
    letter_subset_pred = jp.DICT_SUBSET({'a':'A'})
    path_pred = jp.PathPredicate('items', pred=letter_subset_pred)
    result = path_pred(context, source)

    mismatch_error = jp.TypeMismatchError(
        expect_type=(int, long, float), got_type=str,
        source=source,
        target_path=jp.PATH_SEP.join(['items', 'a']),
        path_value=PathValue('items[1]', numbers))
    valid_result = letter_subset_pred(context, letters).clone_with_source(
        source=source, base_target_path='items', base_value_path='items[0]')
    self.assertEqual(
        # pylint: disable=bad-continuation
        jp.PathPredicateResultBuilder(source, path_pred)
          .add_result_candidate(PathValue('items[0]', letters), valid_result)
          .add_result_candidate(PathValue('items[1]', numbers),
                                mismatch_error)
          .build(True),
        result)

  def test_list_subset_nonstrict_good(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2, 'c':'C'}
    source = [letters, numbers]

    common_subset_pred = jp.LIST_SUBSET([{'c':'C'}])
    self.assertFalse(common_subset_pred.strict)
    self.assertGoodResult(
        PathValue('', source), common_subset_pred,
        common_subset_pred(context, source))

  def test_list_subset_nonstrict_bad(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2, 'c':'C'}
    source = [letters, numbers]

    common_subset_pred = jp.LIST_SUBSET([{'c':3}])

    self.assertEqual(
        jp.PathValueResult(
            valid=False, pred=common_subset_pred,
            source=source, target_path='',
            path_value=PathValue('', source)),
        common_subset_pred(context, source))

  def test_list_subset_strict_good(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2, 'c':'C'}
    source = [letters, numbers]

    common_subset_pred = jp.LIST_SUBSET([letters], strict=True)
    self.assertGoodResult(
        PathValue('', source), common_subset_pred,
        common_subset_pred(context, source))

  def test_list_subset_strict_bad(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2, 'c':'C'}
    source = [letters, numbers]

    common_subset_pred = jp.LIST_SUBSET([{'c':'C'}], strict=True)
    self.assertBadResult(
        PathValue('', source), common_subset_pred,
        common_subset_pred(context, source))

  def test_list_subset_nested_good(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2, 'c':'C'}
    source = [letters, [numbers]]

    pred = jp.LIST_SUBSET([[{'b':2}]])
    self.assertGoodResult(
        PathValue('', source), pred,
        pred(context, source))

  def test_list_subset_nested_bad(self):
    context = ExecutionContext()
    letters = {'a':'A', 'b':'B', 'c':'C'}
    numbers = {'a':1, 'b':2, 'c':'C'}
    source = [numbers, [letters]]

    pred = jp.LIST_SUBSET([[{'b':2}]])
    self.assertBadResult(
        PathValue('', source), pred,
        pred(context, source))

  def test_list_equivalent(self):
    context = ExecutionContext()
    source = [{'a':'A', 'b':'B'}, {'one':1, 'two':2}]
    pred = jp.EQUIVALENT([source[1], source[0]])
    result = pred(context, source)
    self.assertEqual(
        jp.PathValueResult(valid=True, source=source, target_path='',
                           path_value=PathValue('', source),
                           pred=jp.LIST_SIMILAR(pred.operand)),
        result)

  def test_list_equivalent_indirect(self):
    context = ExecutionContext(testB='B', second={'one':1, 'two':2})
    source = [{'a':'A', 'b': lambda x: x['testB']}, lambda x: x['second']]
    actual_source = [{'a':'A', 'b':'B'}, {'one':1, 'two':2}]

    pred = jp.EQUIVALENT(source)
    result = pred(context, actual_source)
    self.assertEqual(
        jp.PathValueResult(valid=True, source=actual_source, target_path='',
                           path_value=PathValue('', actual_source),
                           pred=jp.LIST_SIMILAR(actual_source)),
        result)


if __name__ == '__main__':
  # pylint: disable=invalid-name
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonBinaryPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
