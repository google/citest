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
import citest.json_contract.cardinality_predicate as cp
import citest.json_contract.map_predicate as mp

_CAB = [ 'C', 'A', 'B' ]

_eq_A = jc.STR_EQ('A')
_eq_B = jc.STR_EQ('B')
_eq_X = jc.STR_EQ('X')
_AorX = jc.OR([_eq_A, _eq_X])
_AorB = jc.OR([_eq_A, _eq_B])


class CardinalityPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)

  def test_cardinality_bounds_1(self):
    for min in range(0, 2):
      for max in range(0, 2):
        if min > max:
          continue

        predicate = jc.CardinalityPredicate(_AorX, min=min, max=max)
        expect_ok = min <= 1 and max >= 1

        attempt_a = jc.ObjectResultMapAttempt('A', _AorX('A'))
        attempt_b = jc.ObjectResultMapAttempt('B', _AorX('B'))
        attempt_c = jc.ObjectResultMapAttempt('C', _AorX('C'))
        expect_composite_result = jc.MapPredicateResult(
          valid=expect_ok, pred=_AorX,
          obj_list=_CAB,
          good_map=[attempt_a],
          bad_map=[attempt_c, attempt_b],
          all_results=[attempt_c.result, attempt_a.result, attempt_b.result])

        self.assertEqual(expect_composite_result,
                         jc.MapPredicate(_AorX, min=min, max=max)(_CAB))
        if expect_ok:
          expect_result = cp.ConfirmedCardinalityResult(
            _CAB, 1, predicate, expect_composite_result)
        elif max == 0:
          expect_result = cp.UnexpectedValueCardinalityResult(
            _CAB, 1, predicate, expect_composite_result)
        else:
          expect_result = cp.FailedCardinalityRangeResult(
            _CAB, 1, predicate, expect_composite_result)

        try:
          result = predicate(_CAB)
          self.assertEqual(expect_result, result)
          return
          self.assertEqual(expect_ok, result.__nonzero__())
        except:
          print 'FAILED min={0}, max={1}'.format(min, max)
          raise

  def test_cardinality_bounds_2(self):
    for min in range(0, 2):
      for max in range(0, 2):
        if min > max:
          continue

        predicate = jc.CardinalityPredicate(_AorB, min=min, max=max)
        expect_ok = min <= 2 and max >= 2

        a_attempt = jc.ObjectResultMapAttempt('A', _AorB('A'))
        b_attempt = jc.ObjectResultMapAttempt('B', _AorB('B'))
        c_attempt = jc.ObjectResultMapAttempt('C', _AorB('C'))
        expect_composite_result = jc.MapPredicateResult(
          valid=expect_ok, pred=_AorB,
          obj_list=_CAB,
          good_map=[a_attempt, b_attempt],
          bad_map=[c_attempt],
          all_results=[c_attempt.result, a_attempt.result, b_attempt.result])

        self.assertEqual(expect_composite_result,
                         jc.MapPredicate(_AorB, min=min, max=max)(_CAB))
        if expect_ok:
          expect_result = cp.ConfirmedCardinalityResult(
            _CAB, 2, predicate, expect_composite_result)
        elif max == 0:
          expect_result = cp.UnexpectedValueCardinalityResult(
            _CAB, 2, predicate, expect_composite_result)
        else:
          expect_result = cp.FailedCardinalityRangeResult(
            _CAB, 2, predicate, expect_composite_result)

        try:
          result = predicate(_CAB)
          self.assertEqual(expect_result, result)
          self.assertEqual(expect_ok, result.__nonzero__())
        except:
          print 'FAILED min={0}, max={1}'.format(min, max)
          raise


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(CardinalityPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
