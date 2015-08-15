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
import citest.json_contract as jc


_LETTER_DICT = { 'a':'A', 'b':'B', 'z':'Z' }


class LogicPredicateTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0}\n\nACTUAL\n{1}'.format(a, b)
    super(LogicPredicateTest, self).assertEqual(a, b, msg)

  def test_conjunction_true(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    conjunction = jc.ConjunctivePredicate([aA, bB])
    expect = jc.CompositePredicateResult(
        valid=True, pred=conjunction,
        results=[aA(_LETTER_DICT), bB(_LETTER_DICT)])

    result = conjunction(_LETTER_DICT)
    self.assertTrue(result)
    self.assertEqual(expect, result)

  def test_conjunction_false_aborts_early(self):
    aA = jc.PathEqPredicate('a', 'A')
    b2 = jc.PathEqPredicate('b', 2)
    bB = jc.PathEqPredicate('b', 'B')
    conjunction = jc.ConjunctivePredicate([aA, b2, bB])
    expect = jc.CompositePredicateResult(
        valid=True, pred=conjunction,
        results=[aA(_LETTER_DICT), b2(_LETTER_DICT)])

    result = conjunction(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)

  def test_disjunction_true_aborts_early(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    disjunction = jc.DisjunctivePredicate([aA, bB])
    expect = jc.CompositePredicateResult(
        valid=True, pred=disjunction,
        results=[aA(_LETTER_DICT)])

    result = disjunction(_LETTER_DICT)
    self.assertTrue(result)
    self.assertEqual(expect, result)

  def test_disjunction_false(self):
    a1 = jc.PathEqPredicate('a', 1)
    b2 = jc.PathEqPredicate('b', 2)
    disjunction = jc.DisjunctivePredicate([a1, b2])
    expect = jc.CompositePredicateResult(
        valid=False, pred=disjunction,
        results=[a1(_LETTER_DICT), b2(_LETTER_DICT)])

    result = disjunction(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(LogicPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
