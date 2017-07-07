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


class JsonMatchesPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    try:
      JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)
    except AssertionError:
      print '\nEXPECT\n{0!r}\n\nGOT\n{1!r}\n'.format(expect, have)
      raise

  def test_list_match_defaults(self):
    pred = jp.LIST_MATCHES([jp.NUM_EQ(1)])
    self.assertFalse(pred.strict)
    self.assertFalse(pred.unique)

  def test_list_match_simple_ok(self):
    context = ExecutionContext()
    source = [1, 2]
    want = [jp.NUM_EQ(1)]
    result = jp.LIST_MATCHES(want)(context, source)

    expect = (jp.SequencedPredicateResultBuilder(jp.LIST_MATCHES(want))
              .append_result(jp.MapPredicate(jp.NUM_EQ(1))(context, source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_list_match_simple_bad(self):
    context = ExecutionContext()
    source = [1]
    want = [jp.NUM_NE(1)]
    result = jp.LIST_MATCHES(want)(context, source)

    expect = (jp.SequencedPredicateResultBuilder(jp.LIST_MATCHES(want))
              .append_result(jp.MapPredicate(jp.NUM_NE(1))(context, source))
              .build(False))

    self.assertFalse(result)
    self.assertEquals(expect, result)

  def test_list_match_ok_and_bad(self):
    context = ExecutionContext()
    source = [1, 2, 3]
    want = [jp.NUM_EQ(1), jp.NUM_EQ(-1), jp.NUM_EQ(3)]
    result = jp.LIST_MATCHES(want)(context, source)

    expect = (jp.SequencedPredicateResultBuilder(jp.LIST_MATCHES(want))
              .append_result(jp.MapPredicate(jp.NUM_EQ(1))(context, source))
              .append_result(jp.MapPredicate(jp.NUM_EQ(-1))(context, source))
              .append_result(jp.MapPredicate(jp.NUM_EQ(3))(context, source))
              .build(False))

    self.assertFalse(result)
    self.assertEquals(expect, result)

  def test_list_match_unique_ok(self):
    context = ExecutionContext()
    source = [1, 2]
    want = [jp.NUM_EQ(1)]
    match_pred = jp.LIST_MATCHES(want, unique=True)
    result = match_pred(context, source)

    expect = (jp.SequencedPredicateResultBuilder(match_pred)
              .append_result(jp.MapPredicate(jp.NUM_EQ(1))(context, source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_list_match_unique_bad(self):
    context = ExecutionContext()
    source = [1, 2]
    want = [jp.NUM_EQ(1), jp.NUM_NE(2)]
    match_pred = jp.LIST_MATCHES(want, unique=True)
    result = match_pred(context, source)

    expect = (jp.SequencedPredicateResultBuilder(match_pred)
              .append_result(jp.MapPredicate(jp.NUM_EQ(1))(context, source))
              .append_result(jp.MapPredicate(jp.NUM_NE(2))(context, source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_list_match_strict_ok(self):
    context = ExecutionContext()
    source = [1, 2]
    want = [jp.NUM_NE(0)]
    match_pred = jp.LIST_MATCHES(want, strict=True)
    result = match_pred(context, source)

    expect = (jp.SequencedPredicateResultBuilder(match_pred)
              .append_result(jp.MapPredicate(jp.NUM_NE(0))(context, source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_list_match_strict_bad(self):
    context = ExecutionContext()
    source = [1, 2]
    want = [jp.NUM_NE(2)]
    match_pred = jp.LIST_MATCHES(want, strict=True)
    result = match_pred(context, source)

    expect = (jp.SequencedPredicateResultBuilder(match_pred)
              .append_result(jp.MapPredicate(jp.NUM_NE(2))(context, source))
              .append_result(
                  jp.UnexpectedPathError(
                      source=source, target_path='[1]',
                      path_value=jp.PathValue('[1]', 2)))
              .build(False))

    self.assertFalse(result)
    self.assertEquals(expect, result)

  def _match_dict_attribute_result(self, context, pred, key, value):
    return jp.PathPredicate(key, pred, source_pred=pred,
                            enumerate_terminals=False)(context, value)

  def test_dict_match_simple_ok(self):
    context = ExecutionContext()
    source = {'n' : 10}
    pred = jp.NUM_LE(20)
    want = {'n' : pred}
    result = jp.DICT_MATCHES(want)(context, source)
    expect = (jp.KeyedPredicateResultBuilder(jp.DICT_MATCHES(want))
              .add_result(
                  'n',
                  self._match_dict_attribute_result(
                      context, pred, 'n', source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_dict_match_simple_bad(self):
    context = ExecutionContext()
    source = {'n' : 10}
    pred = jp.NUM_NE(10)
    want = {'n' : pred}
    result = jp.DICT_MATCHES(want)(context, source)

    expect = (jp.KeyedPredicateResultBuilder(jp.DICT_MATCHES(want))
              .add_result(
                  'n',
                  self._match_dict_attribute_result(
                      context, pred, 'n', source))
              .build(False))

    self.assertFalse(result)
    self.assertEquals(expect, result)

  def test_dict_match_multi_ok(self):
    context = ExecutionContext()
    source = {'a' : 'testing', 'n' : 10}
    n_pred = jp.NUM_LE(20)
    a_pred = jp.STR_SUBSTR('test')
    want = {'n' : n_pred, 'a' : a_pred}
    result = jp.DICT_MATCHES(want)(context, source)

    expect = (jp.KeyedPredicateResultBuilder(jp.DICT_MATCHES(want))
              .add_result(
                  'n',
                  self._match_dict_attribute_result(
                      context, n_pred, 'n', source))
              .add_result(
                  'a',
                  self._match_dict_attribute_result(
                      context, a_pred, 'a', source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_dict_match_multi_bad(self):
    context = ExecutionContext()
    source = {'a' : 'testing', 'n' : 10}
    n_pred = jp.NUM_NE(10)
    a_pred = jp.STR_SUBSTR('test')
    want = {'n' : n_pred, 'a' : a_pred}
    result = jp.DICT_MATCHES(want)(context, source)

    expect = (jp.KeyedPredicateResultBuilder(jp.DICT_MATCHES(want))
              .add_result(
                  'n',
                  self._match_dict_attribute_result(
                      context, n_pred, 'n', source))
              .add_result(
                  'a',
                  self._match_dict_attribute_result(
                      context, a_pred, 'a', source))
              .build(False))

    self.assertFalse(result)
    self.assertTrue(result.results['a'])
    self.assertFalse(result.results['n'])
    self.assertEquals(expect, result)

  def test_dict_match_missing_path(self):
    context = ExecutionContext()
    source = {'n' : 10}
    pred = jp.NUM_EQ(10)
    want = {'missing' : pred}
    result = jp.DICT_MATCHES(want)(context, source)

    expect = (jp.KeyedPredicateResultBuilder(jp.DICT_MATCHES(want))
              .add_result(
                  'missing',
                  self._match_dict_attribute_result(
                      context, pred, 'missing', source))
              .build(False))

    self.assertFalse(result)
    self.assertEquals(expect, result)

  def test_dict_match_strict_ok(self):
    context = ExecutionContext()
    source = {'n' : 10}
    pred = jp.NUM_LE(20)
    want = {'n' : pred}
    match_pred = jp.DICT_MATCHES(want, strict=True)
    result = match_pred(context, source)

    expect = (jp.KeyedPredicateResultBuilder(match_pred)
              .add_result(
                  'n',
                  self._match_dict_attribute_result(
                      context, pred, 'n', source))
              .build(True))

    self.assertTrue(result)
    self.assertEquals(expect, result)

  def test_dict_match_strict_bad(self):
    context = ExecutionContext()
    source = {'n' : 10, 'extra' : 'EXTRA'}
    pred = jp.NUM_LE(20)
    want = {'n' : pred}
    match_pred = jp.DICT_MATCHES(want, strict=True)
    result = match_pred(context, source)

    expect = (jp.KeyedPredicateResultBuilder(match_pred)
              .add_result(
                  'n',
                  self._match_dict_attribute_result(
                      context, pred, 'n', source))
              .add_result(
                  'extra',
                  jp.UnexpectedPathError(
                      source=source, target_path='extra',
                      path_value=jp.PathValue('extra', 'EXTRA')))
              .build(False))

    self.assertFalse(result)
    self.assertEquals(expect, result)


if __name__ == '__main__':
  unittest.main()
