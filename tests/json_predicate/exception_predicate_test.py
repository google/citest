# Copyright 2018 Google Inc. All Rights Reserved.
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
# pylint: disable=invalid-name


import unittest

from citest.base import ExecutionContext
import citest.json_predicate as jp


class ExceptionPredicateTest(unittest.TestCase):
  def test_exception_matches(self):
    ex_predicate = jp.ExceptionMatchesPredicate(ValueError, regex='the error')
    self.assertEqual(
        jp.PredicateResult(True, comment='Error matches.'),
        ex_predicate(ExecutionContext(), ValueError('the error')))

  def test_exception_messages_differ(self):
    ex_predicate = jp.ExceptionMatchesPredicate(ValueError, regex='the error')
    self.assertEqual(
        jp.PredicateResult(False, comment='Errors differ.'),
        ex_predicate(ExecutionContext(), ValueError()))

  def test_exception_types_differ(self):
    ex_predicate = jp.ExceptionMatchesPredicate(ValueError, regex='the error')
    self.assertEqual(
        jp.PredicateResult(False, comment='Expected ValueError, got KeyError.'),
        ex_predicate(ExecutionContext(), KeyError('the error')))


if __name__ == '__main__':
  unittest.main()
