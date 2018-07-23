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
# pylint: disable=redefined-builtin


import unittest

from citest.base import (
    ExecutionContext,
    JsonSnapshotHelper)
from citest.json_predicate import PathValue
import citest.json_predicate as jp

_CAB = ['C', 'A', 'B']

# pylint: disable=invalid-name
_eq_A = jp.STR_EQ('A')
_eq_B = jp.STR_EQ('B')
_eq_X = jp.STR_EQ('X')
_AorX = jp.OR([_eq_A, _eq_X])
_AorB = jp.OR([_eq_A, _eq_B])


class CardinalityPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    try:
      JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)
    except AssertionError:
      print('\nEXPECT\n{0!r}\n\nGOT\n{1!r}\n'.format(expect, have))
      raise

  def test_cardinality_bounds_1(self):
    context = ExecutionContext()
    for min in range(0, 3):
      for max in range(0, 3):
        if min > max:
          continue

        predicate = jp.CardinalityPredicate(_AorX, min=min, max=max)
        expect_ok = min <= 1 and max >= 1

        source = _CAB
        result = predicate(context, source)

        all_results = [
            jp.SequencedPredicateResult(
                False, _AorX,
                [jp.PathValueResult(_CAB, '', PathValue('[0]', 'C'),
                                    valid=False, pred=_eq_A),
                 jp.PathValueResult(_CAB, '', PathValue('[0]', 'C'),
                                    valid=False, pred=_eq_X)]),
            jp.SequencedPredicateResult(
                True, _AorX,
                [jp.PathValueResult(_CAB, '', PathValue('[1]', 'A'),
                                    valid=True, pred=_eq_A)]),
            jp.SequencedPredicateResult(
                False, _AorX,
                [jp.PathValueResult(_CAB, '', PathValue('[2]', 'B'),
                                    valid=False, pred=_eq_A),
                 jp.PathValueResult(_CAB, '', PathValue('[2]', 'B'),
                                    valid=False, pred=_eq_X)])]

        builder = jp.PathPredicateResultBuilder(
            pred=jp.PathPredicate('', _AorX), source=_CAB)
        builder.add_result_candidate(PathValue('[0]', 'C'), all_results[0])
        builder.add_result_candidate(PathValue('[1]', 'A'), all_results[1])
        builder.add_result_candidate(PathValue('[2]', 'B'), all_results[2])

        expect_path_result = builder.build(True)
        if expect_ok:
          self.assertEqual(
              jp.ConfirmedCardinalityResult(predicate, expect_path_result),
              result)
        elif max == 0:
          self.assertEqual(
              jp.UnexpectedValueCardinalityResult(
                  predicate, expect_path_result),
              result)
        else:
          self.assertEqual(
              jp.FailedCardinalityRangeResult(
                  predicate, expect_path_result),
              result)

  def test_cardinality_bounds_2_indirect(self):
    predicate = jp.CardinalityPredicate(_AorB,
                                        min=lambda x: x['min'],
                                        max=lambda x: x['max'])
    for min in range(0, 3):
      for max in range(0, 3):
        if min > max:
          continue

        context = ExecutionContext(min=min, max=max)
        expect_ok = min <= 2 and max >= 2

        source = _CAB
        result = predicate(context, source)

        all_results = [
            jp.SequencedPredicateResult(
                False, _AorB,
                [jp.PathValueResult(_CAB, '', PathValue('[0]', 'C'),
                                    valid=False, pred=_eq_A),
                 jp.PathValueResult(_CAB, '', PathValue('[0]', 'C'),
                                    valid=False, pred=_eq_B)]),
            jp.SequencedPredicateResult(
                True, _AorB,
                [jp.PathValueResult(_CAB, '', PathValue('[1]', 'A'),
                                    valid=True, pred=_eq_A)]),
            jp.SequencedPredicateResult(
                True, _AorB,
                [jp.PathValueResult(_CAB, '', PathValue('[2]', 'B'),
                                    valid=False, pred=_eq_A),
                 jp.PathValueResult(_CAB, '', PathValue('[2]', 'B'),
                                    valid=True, pred=_eq_B)])]

        builder = jp.PathPredicateResultBuilder(
            pred=jp.PathPredicate('', _AorB), source=_CAB)
        builder.add_result_candidate(PathValue('[0]', 'C'), all_results[0])
        builder.add_result_candidate(PathValue('[1]', 'A'), all_results[1])
        builder.add_result_candidate(PathValue('[2]', 'B'), all_results[2])
        expect_path_result = builder.build(True)

        if expect_ok:
          self.assertEqual(
              jp.ConfirmedCardinalityResult(predicate, expect_path_result),
              result)
        elif max == 0:
          self.assertEqual(
              jp.UnexpectedValueCardinalityResult(
                  predicate, expect_path_result),
              result)
        else:
          self.assertEqual(
              jp.FailedCardinalityRangeResult(
                  predicate, expect_path_result),
              result)


if __name__ == '__main__':
  unittest.main()
