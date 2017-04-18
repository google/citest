# Copyright 2016 Google Inc. All Rights Reserved.
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


"""Tests the citest.json_predicate.path_predicate_result module."""


import unittest

from citest.base import ExecutionContext
from citest.json_predicate import (
    PathPredicate,
    PathPredicateResult,
    PathPredicateResultBuilder,
    PathPredicateResultCandidate,
    PathValue,
    )

class JsonPathPredicateResultTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0!r}\nGOT\n{1!r}'.format(a, b)
    super(JsonPathPredicateResultTest, self).assertEqual(a, b, msg)

  def test_path_predicate_eq(self):
    pred_a = PathPredicate('x')
    pred_b = PathPredicate('y')
    self.assertNotEqual(pred_a, pred_b)

    pred_a = PathPredicate('x')
    pred_b = PathPredicate('x')
    self.assertEqual(pred_a, pred_b)

    pred_a = PathPredicate('x', pred=PathPredicate('X'))
    self.assertNotEqual(pred_a, pred_b)

    pred_b = PathPredicate('x', pred=PathPredicate('X'))
    self.assertEqual(pred_a, pred_b)

  def test_path_predicate_result_eq(self):
    context = ExecutionContext()
    source = {}
    path_pred = PathPredicate('x')
    a_result = path_pred(context, source)  # this is just something well formed.

    result_a = PathPredicateResult(
        True, path_pred, source,
        valid_candidates=[], invalid_candidates=[])
    result_b = PathPredicateResult(
        True, path_pred, source,
        valid_candidates=[], invalid_candidates=[])
    self.assertEqual(result_a, result_b)

    # Only valid different.
    result_b = PathPredicateResult(
        False, path_pred, source,
        valid_candidates=[], invalid_candidates=[])
    self.assertNotEqual(result_a, result_b)

    # Only filter different.
    result_b = PathPredicateResult(
        True, PathPredicate('y'), source,
        valid_candidates=[], invalid_candidates=[])
    self.assertNotEqual(result_a, result_b)

    # Only source different.
    result_b = PathPredicateResult(
        True, path_pred, [source],
        valid_candidates=[], invalid_candidates=[])
    self.assertNotEqual(result_a, result_b)

    # Only valid candidates different.
    result_b = PathPredicateResult(
        True, path_pred, source,
        valid_candidates=[
            PathPredicateResultCandidate(PathValue('x', 0), a_result)],
        invalid_candidates=[])
    self.assertNotEqual(result_a, result_b)

    # Only invalid candidates different.
    result_b = PathPredicateResult(
        True, path_pred, source,
        valid_candidates=[],
        invalid_candidates=[
            PathPredicateResultCandidate(PathValue('x', 0), a_result)])
    self.assertNotEqual(result_a, result_b)

    # More fully defined equal.
    result_a = PathPredicateResult(
        True, path_pred, source,
        valid_candidates=[
            PathPredicateResultCandidate(PathValue('x', 0), a_result)],
        invalid_candidates=[
            PathPredicateResultCandidate(PathValue('x', 0), a_result)])
    result_b = PathPredicateResult(
        True, path_pred, source,
        valid_candidates=[
            PathPredicateResultCandidate(PathValue('x', 0), a_result)],
        invalid_candidates=[
            PathPredicateResultCandidate(PathValue('x', 0), a_result)])
    self.assertEqual(result_a, result_b)


  def test_path_predicate_result_builder(self):
    source = {}
    for valid in [True, False]:
      for path_pred in [PathPredicate('x'), None]:
        builder = PathPredicateResultBuilder(source, path_pred)
        self.assertEqual(PathPredicateResult(valid, path_pred, source,
                                             valid_candidates=[],
                                             invalid_candidates=[]),
                         builder.build(valid))

if __name__ == '__main__':
  unittest.main()
