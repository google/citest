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

from citest.base.scribe import Scribe
import citest.json_contract as jc
import citest.json_contract.cardinality_predicate as cp
import citest.json_contract.map_predicate as mp

_CAB = [ 'C', 'A', 'B' ]

_eq_A = jc.STR_EQ('A')
_eq_B = jc.STR_EQ('B')
_eq_X = jc.STR_EQ('X')
_AorX = jc.DisjunctivePredicate([_eq_A, _eq_X])
_AorB = jc.DisjunctivePredicate([_eq_A, _eq_B])


class CardinalityPredicateTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      scribe = Scribe()
      msg = 'EXPECT\n{0}\nGOT\n{1}'.format(
        scribe.render_to_string(a), scribe.render_to_string(b))
    super(CardinalityPredicateTest, self).assertEqual(a, b, msg)


  def test_cardinality_bounds_1(self):
    for min in range(0, 2):
      for max in range(0, 2):
        if min > max:
          continue

        predicate = jc.CardinalityPredicate(_AorX, min=min, max=max)
        expect_ok = min <= 1 and max >= 1

        expect_composite_result = jc.MapPredicateResult(
          valid=expect_ok, pred=_AorX,
          obj_list=_CAB,
          good_map=[
            jc.ObjectResultMapAttempt('A', _AorX('A'))],
          bad_map=[
            jc.ObjectResultMapAttempt('C', _AorX('C')),
            jc.ObjectResultMapAttempt('B', _AorX('B'))],
          all_results=[_AorX('C'), _AorX('A'), _AorX('B')])

        self.assertEqual(expect_composite_result,
                         jc.MapPredicate(_AorX)(_CAB))
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

        expect_composite_result = jc.MapPredicateResult(
          valid=expect_ok, pred=_AorB,
          obj_list=_CAB,
          good_map=[
            jc.ObjectResultMapAttempt('A', _AorB('A')),
            jc.ObjectResultMapAttempt('B', _AorB('B'))],
          bad_map=[
            jc.ObjectResultMapAttempt('C', _AorB('C'))],
          all_results=[_AorB('C'), _AorB('A'), _AorB('B')])

        self.assertEqual(expect_composite_result,
                         jc.MapPredicate(_AorB)(_CAB))
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
