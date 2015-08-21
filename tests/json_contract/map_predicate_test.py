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

from citest.base import Scribe
import citest.json_contract as jc
import citest.json_contract.map_predicate as mp


_LETTER_DICT = { 'a':'A', 'b':'B', 'z':'Z' }
_NUMBER_DICT = { 'a':1, 'b':2, 'three':3 }
_MIXED_DICT  = {'a':'A', 'b':2, 'x':'X'}
_COMPOSITE_DICT = { 'letters': _LETTER_DICT, 'numbers': _NUMBER_DICT }

_LETTER_ARRAY = ['a', 'b', 'c']
_NUMBER_ARRAY = [1, 2, 3]
_DICT_ARRAY = [{}, _LETTER_DICT, _NUMBER_DICT, _COMPOSITE_DICT]
_MULTI_ARRAY = [ _LETTER_DICT, _NUMBER_DICT, _LETTER_DICT, _NUMBER_DICT]


class JsonMapPredicateTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECT\n{0}\nGOT\n{1}'.format(a, b)
    super(JsonMapPredicateTest, self).assertEqual(a, b, msg)

  def _try_map(self, pred, obj, expect_ok, expect_map_result=None,
                  dump=False, min=1):
    """Helper function for invoking finder and asserting the result.

    Args:
      pred: The jc.ValuePredicate to map.
      obj: The object to apply the predicate to.
      expect_ok: Whether we expect apply to succeed or not.
      expect_map_result: If not None, then the expected
          mp.MapPredicateResult from apply().
      dump: If True then print the filter_result to facilitate debugging.
    """
    map_result = jc.MapPredicate(pred, min=min)(obj)
    if dump:
      print 'MAP_RESULT:\n{0}\n'.format(Scribe().render_to_string(map_result))

    if expect_map_result:
      self.assertEqual(
        expect_map_result, map_result,
        '\nEXPECT {0}\n\nACTUAL {1}'.format(
            expect_map_result, map_result))
    error_msg = '{expect_ok} != {ok}\n{map_result}'.format(
      expect_ok=expect_ok, ok=map_result.__nonzero__(),
      map_result=map_result)
    self.assertEqual(expect_ok, map_result.__nonzero__(), error_msg)

  def test_map_predicate_good_1(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))

    expect_result = mp.MapPredicateResult(
      valid=True, pred=aA,
      obj_list=[_LETTER_DICT], all_results=[aA(_LETTER_DICT)],
      good_map=[mp.ObjectResultMapAttempt(_LETTER_DICT, aA(_LETTER_DICT))],
      bad_map=[])

    self._try_map(aA, _LETTER_DICT, True, expect_result)

  def test_map_predicate_bad(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))

    expect_result = mp.MapPredicateResult(
      valid=True, pred=aA,
      obj_list=[_NUMBER_DICT], all_results=[aA(_NUMBER_DICT)],
      bad_map=[mp.ObjectResultMapAttempt(_NUMBER_DICT, aA(_NUMBER_DICT))],
      good_map=[])

    self._try_map(aA, _NUMBER_DICT, False, expect_result)

  def test_map_predicate_good_and_bad_min_1(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))

    expect_result = mp.MapPredicateResult(
      valid=True, pred=aA,
      obj_list=[_NUMBER_DICT, _LETTER_DICT],
      all_results=[aA(_NUMBER_DICT), aA(_LETTER_DICT)],
      good_map=[mp.ObjectResultMapAttempt(_LETTER_DICT, aA(_LETTER_DICT))],
      bad_map=[mp.ObjectResultMapAttempt(_NUMBER_DICT, aA(_NUMBER_DICT))])

    self._try_map(aA, [_NUMBER_DICT, _LETTER_DICT], True, expect_result)

  def test_map_predicate_good_and_bad_min_2(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))

    expect_result = mp.MapPredicateResult(
      valid=False, pred=aA,
      obj_list=[_NUMBER_DICT, _LETTER_DICT],
      all_results=[aA(_NUMBER_DICT), aA(_LETTER_DICT)],
      good_map=[mp.ObjectResultMapAttempt(_LETTER_DICT, aA(_LETTER_DICT))],
      bad_map=[mp.ObjectResultMapAttempt(_NUMBER_DICT, aA(_NUMBER_DICT))])

    self._try_map(
      aA, [_NUMBER_DICT, _LETTER_DICT], False, expect_result, min=2)

  def test_map_not_found(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))

    expect_result = mp.MapPredicateResult(
      valid=True, pred=aA,
      obj_list=[_COMPOSITE_DICT], all_results=[aA(_COMPOSITE_DICT)],
      bad_map=[mp.ObjectResultMapAttempt(_COMPOSITE_DICT,
                                          aA(_COMPOSITE_DICT))],
      good_map=[])

    self._try_map(aA, _COMPOSITE_DICT, False, expect_result)

  def test_object_filter_cases(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))

    self._try_map(aA, _LETTER_DICT, True)
    self._try_map(aA, _COMPOSITE_DICT, False)
    self._try_map(aA, _NUMBER_DICT, False)
    self._try_map(aA, _MULTI_ARRAY, True)
    self._try_map(aA, [_COMPOSITE_DICT, _COMPOSITE_DICT], False)
    self._try_map(aA, _MIXED_DICT, True)

    AandB = jc.ConjunctivePredicate(
               [jc.PathEqPredicate('a', 'A'),
                jc.PathEqPredicate('b', 'B')])
    self._try_map(AandB, _LETTER_DICT, True)
    self._try_map(AandB, _COMPOSITE_DICT, False)
    self._try_map(AandB, _NUMBER_DICT, False)
    self._try_map(AandB, _MULTI_ARRAY, True)
    self._try_map(AandB, _MIXED_DICT, False)


  def test_none_bad(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))
    self._try_map(aA, None, False)

  def test_none_good(self):
    aA = jc.PathPredicate('a', jc.STR_EQ('A'))
    self._try_map(aA, None, True, min=0)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonMapPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
