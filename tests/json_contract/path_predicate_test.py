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


import unittest

from citest.base import JsonSnapshotHelper
import citest.json_contract as jc


_LETTER_ARRAY = ['a', 'b', 'c']
_LETTER_DICT = {'a': 'A', 'b': 'B', 'z': 'Z'}
_NUMBER_DICT = {'a': 1, 'b': 2, 'three': 3}
_COMPOSITE_DICT = { 'letters': _LETTER_DICT, 'numbers': _NUMBER_DICT }


def _make_found(source, path_trace, pred, valid=True):
  value = path_trace[len(path_trace) - 1].value if path_trace else source
  path = '/'.join([elem.path for elem in path_trace])
  if not path:
    path = None
  return jc.JsonFoundValueResult(path=path, source=source, value=value,
                                 pred=pred, valid=valid, path_trace=path_trace)


class JsonPathPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)

  def test_clone_type_mismatch_none_context(self):
    result = jc.JsonTypeMismatchResult(list, dict, 'ORIGINAL')
    path_trace=[jc.PathValue('some/path', 'ORIGINAL')]
    self.assertEqual(
        jc.JsonTypeMismatchResult(list, dict, source='ACTUAL', path='some/path',
                                  path_trace=path_trace),
        result.clone_in_context('ACTUAL', 'some/path'))

  def test_clone_type_mismatch_context(self):
    result = jc.JsonTypeMismatchResult(
        list, dict, source='ORIGINAL', path='inner/path')
    new_path_trace = ['some/path', 'ORIGINAL']
    self.assertEqual(
        jc.JsonTypeMismatchResult(
            list, dict, source='ACTUAL', path='some/path/inner/path',
            path_trace=[jc.PathValue('some/path', 'ORIGINAL')]),
        result.clone_in_context('ACTUAL', 'some/path'))

  def test_clone_value_result_none_context(self):
    pred = jc.STR_EQ('WANT')
    result = jc.JsonFoundValueResult(valid=True, pred=pred, value='GOT')
    self.assertEqual(
        jc.JsonFoundValueResult(
            source='ACTUAL', path='some/path', pred=pred, value='GOT',
            path_trace=[jc.PathValue('some/path', 'GOT')]),
        result.clone_in_context('ACTUAL', 'some/path'))

  def test_clone_value_result_valid_context(self):
    pred = jc.STR_EQ('WANT')
    original_path_trace = [jc.PathValue('original/path', 'GOT')]
    result = jc.JsonFoundValueResult(
        valid=False, source='ORIGINAL', path='original/path',
        pred=pred, value='GOT', path_trace=original_path_trace)
    new_path_trace = ([jc.PathValue('some/other', 'ORIGINAL')]
                      + original_path_trace)
    self.assertEqual(
        jc.JsonFoundValueResult(
            valid=False,
            source='ACTUAL', path='some/other/original/path',
            pred=pred, value='GOT', path_trace=new_path_trace),
        result.clone_in_context('ACTUAL', 'some/other'))

  def test_path_found(self):
    pred = jc.PathPredicate('outer/inner')
    d = {'outer': {'inner': {'a': 'A', 'b':'B'}}}
    expect = jc.JsonFoundValueResult(
        valid=True, source=d, path='outer/inner', pred=None,
        value={'a': 'A', 'b':'B'},
        path_trace=[jc.PathValue('outer', d['outer']),
                    jc.PathValue('inner', d['outer']['inner'])])
    self.assertEqual(expect, pred(d))

  def test_path_predicate_wrappers(self):
    pred = jc.PathEqPredicate('parent/child', 'VALUE')
    self.assertEqual(pred, jc.PathEqPredicate('parent/child', 'VALUE'))
    self.assertNotEqual(pred, jc.PathEqPredicate('parent/child2', 'VALUE'))
    self.assertNotEqual(pred, jc.PathEqPredicate('parent/child', 'VALUE2'))
    self.assertNotEqual(pred, jc.PathContainsPredicate('parent/child', 'VALUE'))

  def test_path_value_found_top(self):
    pred = jc.PathEqPredicate('letters', _LETTER_DICT)
    result = pred(_COMPOSITE_DICT)

    self.assertTrue(result)
    self.assertEqual(
        _make_found(
            _COMPOSITE_DICT, path_trace=[jc.PathValue('letters', _LETTER_DICT)],
            pred=jc.DICT_EQ(_LETTER_DICT)),
        result)

  def test_path_value_found_nested(self):
    pred = jc.PathEqPredicate('letters/a', 'A')
    result = pred(_COMPOSITE_DICT)

    self.assertTrue(result)
    self.assertEqual(
      _make_found(
          _COMPOSITE_DICT,
          path_trace=[
              jc.PathValue('letters', _LETTER_DICT),
              jc.PathValue('a', 'A')],
          pred=jc.STR_EQ('A')),
      result)

  def test_path_value_not_found(self):
    pred = jc.PathEqPredicate('letters/a', 'B')
    result = pred(_COMPOSITE_DICT)

    self.assertEqual(
      _make_found(
          _COMPOSITE_DICT,
          path_trace=[
              jc.PathValue('letters', _LETTER_DICT),
              jc.PathValue('a', 'A')],
          pred=jc.STR_EQ('B'),
          valid=False),
      result)

  def test_path_contains(self):
    container = { 'parent':_COMPOSITE_DICT }

    self.assertTrue(
        jc.PathContainsPredicate('parent/letters/b', 'B')(container))

    self.assertTrue(
        jc.PathContainsPredicate('parent/letters', {'b':'B'})(container))

    self.assertTrue(
        jc.PathContainsPredicate('parent', {'letters':{'b':'B'}})(container))

    container = { 'parent': [ _LETTER_DICT, _NUMBER_DICT, _COMPOSITE_DICT ] }

    self.assertTrue(
        jc.PathContainsPredicate('parent/numbers', {'b':2})(container))

    container = {'first':[{'second': [{'a':[1, 2, 3], 'b':[4, 5, 6]} ]} ]}
    self.assertTrue(jc.PathContainsPredicate('first/second/b', [5])(container))

    jc.PathContainsPredicate('first/second', {'b': [5]})(container)

  def test_path_elements_contain(self):
    container = { 'parent': {'numbers':_NUMBER_DICT} }
    self.assertTrue(
       jc.PathElementsContainPredicate('parent', {'numbers':{'b':2}})(container))

    container = { 'parent': {'array':_LETTER_ARRAY} }
    self.assertTrue(
        jc.PathElementsContainPredicate('parent/array', 'b')(container))

    container = {'first':[{'second': [{'a':[1, 2, 3], 'b':[4, 5, 6]} ]} ]}
    self.assertTrue(
        jc.PathElementsContainPredicate('first/second', {'b': 5})(container))

  def test_path_does_not_contain(self):
    container = { 'parent':_COMPOSITE_DICT }

    # We're going to ignore this, so will just let it accumulate.
    self.assertFalse(jc.PathContainsPredicate(
        'parent/letters/a', 'B')(container))
    self.assertFalse(jc.PathContainsPredicate(
        'parent/letters/X', 'X')(container))

    self.assertFalse(
        jc.PathContainsPredicate('parent/letters', {'b':'X'})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent/letters', {'X':'X'})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent', {'letters':{'b':'X'}})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent', {'letters':{'X':'X'}})(container))

  def test_predicate_without_path(self):
    pred = jc.PathPredicate(None, jc.STR_EQ('X'))
    result = pred('X')
    self.assertTrue(result)
    self.assertEqual(
      _make_found('X', path_trace=[], pred=jc.STR_EQ('X'), valid=True), result)

  def test_path_predicate_wrappers(self):
    pred = jc.PathEqPredicate('parent/child', 'VALUE')
    self.assertEqual(pred, jc.PathEqPredicate('parent/child', 'VALUE'))
    self.assertNotEqual(pred, jc.PathEqPredicate('parent/child2', 'VALUE'))
    self.assertNotEqual(pred, jc.PathEqPredicate('parent/child', 'VALUE2'))
    self.assertNotEqual(pred, jc.PathContainsPredicate('parent/child', 'VALUE'))

  def test_path_value_found_top(self):
    pred = jc.PathEqPredicate('letters', _LETTER_DICT)
    result = pred(_COMPOSITE_DICT)

    self.assertTrue(result)
    self.assertEqual(
        _make_found(
            _COMPOSITE_DICT, path_trace=[jc.PathValue('letters', _LETTER_DICT)],
            pred=jc.DICT_EQ(_LETTER_DICT)),
        result)

  def test_path_value_found_nested(self):
    pred = jc.PathEqPredicate('letters/a', 'A')
    result = pred(_COMPOSITE_DICT)

    self.assertTrue(result)
    self.assertEqual(
      _make_found(
          _COMPOSITE_DICT,
          path_trace=[
              jc.PathValue('letters', _LETTER_DICT),
              jc.PathValue('a', 'A')],
          pred=jc.STR_EQ('A')),
      result)

  def test_path_value_not_found(self):
    pred = jc.PathEqPredicate('letters/a', 'B')
    result = pred(_COMPOSITE_DICT)

    self.assertEqual(
      _make_found(
          _COMPOSITE_DICT,
          path_trace=[
              jc.PathValue('letters', _LETTER_DICT),
              jc.PathValue('a', 'A')],
          pred=jc.STR_EQ('B'),
          valid=False),
      result)

  def test_path_contains(self):
    container = { 'parent':_COMPOSITE_DICT }

    self.assertTrue(
        jc.PathContainsPredicate('parent/letters/b', 'B')(container))

    self.assertTrue(
        jc.PathContainsPredicate('parent/letters', {'b':'B'})(container))

    self.assertTrue(
        jc.PathContainsPredicate('parent', {'letters':{'b':'B'}})(container))

    container = { 'parent': [ _LETTER_DICT, _NUMBER_DICT, _COMPOSITE_DICT ] }

    self.assertTrue(
        jc.PathContainsPredicate('parent/numbers', {'b':2})(container))

    container = {'first':[{'second': [{'a':[1, 2, 3], 'b':[4, 5, 6]} ]} ]}
    self.assertTrue(jc.PathContainsPredicate('first/second/b', [5])(container))

    jc.PathContainsPredicate('first/second', {'b': [5]})(container)

  def test_path_elements_contain(self):
    container = { 'parent': {'numbers':_NUMBER_DICT} }
    self.assertTrue(
       jc.PathElementsContainPredicate('parent', {'numbers':{'b':2}})(container))

    container = { 'parent': {'array':_LETTER_ARRAY} }
    self.assertTrue(
        jc.PathElementsContainPredicate('parent/array', 'b')(container))

    container = {'first':[{'second': [{'a':[1, 2, 3], 'b':[4, 5, 6]} ]} ]}
    self.assertTrue(
        jc.PathElementsContainPredicate('first/second', {'b': 5})(container))

  def test_path_does_not_contain(self):
    container = { 'parent':_COMPOSITE_DICT }

    # We're going to ignore this, so will just let it accumulate.
    self.assertFalse(jc.PathContainsPredicate(
        'parent/letters/a', 'B')(container))
    self.assertFalse(jc.PathContainsPredicate(
        'parent/letters/X', 'X')(container))

    self.assertFalse(
        jc.PathContainsPredicate('parent/letters', {'b':'X'})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent/letters', {'X':'X'})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent', {'letters':{'b':'X'}})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent', {'letters':{'X':'X'}})(container))

  def test_predicate_without_path(self):
    pred = jc.PathPredicate(None, jc.STR_EQ('X'))
    result = pred('X')
    self.assertTrue(result)
    self.assertEqual(
      _make_found('X', path_trace=[], pred=jc.STR_EQ('X'), valid=True), result)


  def test_path_predicate_wrappers(self):
    pred = jc.PathEqPredicate('parent/child', 'VALUE')
    self.assertEqual(pred, jc.PathEqPredicate('parent/child', 'VALUE'))
    self.assertNotEqual(pred, jc.PathEqPredicate('parent/child2', 'VALUE'))
    self.assertNotEqual(pred, jc.PathEqPredicate('parent/child', 'VALUE2'))
    self.assertNotEqual(pred, jc.PathContainsPredicate('parent/child', 'VALUE'))

  def test_path_value_found_top(self):
    pred = jc.PathEqPredicate('letters', _LETTER_DICT)
    result = pred(_COMPOSITE_DICT)

    self.assertTrue(result)
    self.assertEqual(
        _make_found(
            _COMPOSITE_DICT, path_trace=[jc.PathValue('letters', _LETTER_DICT)],
            pred=jc.DICT_EQ(_LETTER_DICT)),
        result)

  def test_path_value_found_nested(self):
    pred = jc.PathEqPredicate('letters/a', 'A')
    result = pred(_COMPOSITE_DICT)

    self.assertTrue(result)
    self.assertEqual(
      _make_found(
          _COMPOSITE_DICT,
          path_trace=[
              jc.PathValue('letters', _LETTER_DICT),
              jc.PathValue('a', 'A')],
          pred=jc.STR_EQ('A')),
      result)

  def test_path_value_not_found(self):
    pred = jc.PathEqPredicate('letters/a', 'B')
    result = pred(_COMPOSITE_DICT)

    self.assertEqual(
      _make_found(
          _COMPOSITE_DICT,
          path_trace=[
              jc.PathValue('letters', _LETTER_DICT),
              jc.PathValue('a', 'A')],
          pred=jc.STR_EQ('B'),
          valid=False),
      result)

  def test_path_contains(self):
    container = { 'parent':_COMPOSITE_DICT }

    self.assertTrue(
        jc.PathContainsPredicate('parent/letters/b', 'B')(container))

    self.assertTrue(
        jc.PathContainsPredicate('parent/letters', {'b':'B'})(container))

    self.assertTrue(
        jc.PathContainsPredicate('parent', {'letters':{'b':'B'}})(container))

    container = { 'parent': [ _LETTER_DICT, _NUMBER_DICT, _COMPOSITE_DICT ] }

    self.assertTrue(
        jc.PathContainsPredicate('parent/numbers', {'b':2})(container))

    container = {'first':[{'second': [{'a':[1, 2, 3], 'b':[4, 5, 6]} ]} ]}
    self.assertTrue(jc.PathContainsPredicate('first/second/b', [5])(container))

    jc.PathContainsPredicate('first/second', {'b': [5]})(container)

  def test_path_elements_contain(self):
    container = { 'parent': {'numbers':_NUMBER_DICT} }
    self.assertTrue(
       jc.PathElementsContainPredicate('parent', {'numbers':{'b':2}})(container))

    container = { 'parent': {'array':_LETTER_ARRAY} }
    self.assertTrue(
        jc.PathElementsContainPredicate('parent/array', 'b')(container))

    container = {'first':[{'second': [{'a':[1, 2, 3], 'b':[4, 5, 6]} ]} ]}
    self.assertTrue(
        jc.PathElementsContainPredicate('first/second', {'b': 5})(container))

  def test_path_does_not_contain(self):
    container = { 'parent':_COMPOSITE_DICT }

    # We're going to ignore this, so will just let it accumulate.
    self.assertFalse(jc.PathContainsPredicate(
        'parent/letters/a', 'B')(container))
    self.assertFalse(jc.PathContainsPredicate(
        'parent/letters/X', 'X')(container))

    self.assertFalse(
        jc.PathContainsPredicate('parent/letters', {'b':'X'})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent/letters', {'X':'X'})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent', {'letters':{'b':'X'}})(container))
    self.assertFalse(
        jc.PathContainsPredicate('parent', {'letters':{'X':'X'}})(container))

  def test_predicate_without_path(self):
    pred = jc.PathPredicate(None, jc.STR_EQ('X'))
    result = pred('X')
    self.assertTrue(result)
    self.assertEqual(
      _make_found('X', path_trace=[], pred=jc.STR_EQ('X'), valid=True), result)

if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonPathPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
