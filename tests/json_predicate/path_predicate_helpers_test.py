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

# pylint: disable=missing-docstring


import unittest

from citest.base import JsonSnapshotHelper
from citest.json_predicate import PATH_SEP, PathValue
import citest.json_predicate as jp


_LETTER_ARRAY = ['a', 'b', 'c']
_LETTER_DICT = {'a': 'A', 'b': 'B', 'z': 'Z'}
_NUMBER_DICT = {'a': 1, 'b': 2, 'three': 3}
_COMPOSITE_DICT = {'letters': _LETTER_DICT, 'numbers': _NUMBER_DICT}


def _make_result(use_pred, inner_pred, source, good, invalid, pruned=None):
  builder = jp.PathPredicateResultBuilder(source, use_pred)
  builder.add_all_path_failures(pruned or [])

  for path_value in good:
    builder.add_result_candidate(
        path_value,
        jp.PathValueResult(source=source, target_path=path_value.path,
                           pred=inner_pred, valid=True, path_value=path_value))
  for result in invalid:
    path_value = result.path_value
    builder.add_result_candidate(path_value, result)

  return builder.build(len(good) > 0)


class JsonPathPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    try:
      JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)
    except AssertionError:
      print '\nEXPECT\n{0!r}\n\nGOT\n{1!r}\n'.format(expect, have)
      raise

  def test_path_value_found_top(self):
    source = _COMPOSITE_DICT
    pred = jp.PathEqPredicate('letters', _LETTER_DICT)
    result = pred(source)
    expect = _make_result(pred, jp.DICT_EQ(_LETTER_DICT), source,
                          [PathValue('letters', _LETTER_DICT)],
                          [])
    self.assertTrue(result)
    self.assertEqual(expect, result)

  def test_path_found_in_array(self):
    pred = jp.PathPredicate(PATH_SEP.join(['outer', 'inner', 'a']))
    simple = {'a': 'A', 'b': 'B'}
    source = {'outer': [{'middle': simple}, {'inner': simple}]}
    found = [PathValue(PATH_SEP.join(['outer[1]', 'inner', 'a']), 'A')]
    pruned = [
        jp.MissingPathError(
            source['outer'][0], 'inner',
            path_value=PathValue('outer[0]', source['outer'][0]))]

    expect = _make_result(pred, None, source, found, [], pruned)
    self.assertEqual(expect, pred(source))

  def test_path_found_multiple(self):
    source = {'outer': [_LETTER_DICT, _NUMBER_DICT]}
    pred = jp.PathPredicate(PATH_SEP.join(['outer', 'a']))
    result = pred(source)
    self.assertEqual(
        _make_result(
            pred, None, source,
            [PathValue(PATH_SEP.join(['outer[0]', 'a']), 'A'),
             PathValue(PATH_SEP.join(['outer[1]', 'a']), 1)],
            []),
        result)

  def test_path_value_found_nested(self):
    source = _COMPOSITE_DICT
    pred = jp.PathEqPredicate(PATH_SEP.join(['letters', 'a']), 'A')
    result = pred(source)

    self.assertEqual(
        _make_result(
            pred, jp.STR_EQ('A'), source,
            [PathValue(PATH_SEP.join(['letters', 'a']), 'A')], []),
        result)
    self.assertTrue(result)

  def test_path_value_not_found(self):
    source = _COMPOSITE_DICT
    pred = jp.PathEqPredicate(PATH_SEP.join(['letters', 'a']), 'B')
    result = pred(source)
    self.assertEqual(
        _make_result(
            pred, jp.STR_EQ('B'), source, [],
            [jp.PathValueResult(
                pred=jp.STR_EQ('B'),
                path_value=PathValue(PATH_SEP.join(['letters', 'a']), 'A'),
                source=_COMPOSITE_DICT,
                target_path=PATH_SEP.join(['letters', 'a']))]),
        result)


if __name__ == '__main__':
  # pylint: disable=invalid-name
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonPathPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
