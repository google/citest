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
from citest.base import Scribe


_LETTER_DICT = { 'a':'A', 'b':'B', 'z':'Z' }


class LogicPredicateTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0}\n\nACTUAL\n{1}'.format(
          Scribe().render_to_string(a),
          Scribe().render_to_string(b))
    super(LogicPredicateTest, self).assertEqual(a, b, msg)

  def test_conjunction_true(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    conjunction = jc.AND([aA, bB])
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
    conjunction = jc.AND([aA, b2, bB])
    expect = jc.CompositePredicateResult(
        valid=True, pred=conjunction,
        results=[aA(_LETTER_DICT), b2(_LETTER_DICT)])

    result = conjunction(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)

  def test_disjunction_true_aborts_early(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    disjunction = jc.OR([aA, bB])
    expect = jc.CompositePredicateResult(
        valid=True, pred=disjunction,
        results=[aA(_LETTER_DICT)])

    result = disjunction(_LETTER_DICT)
    self.assertTrue(result)
    self.assertEqual(expect, result)

  def test_disjunction_false(self):
    a1 = jc.PathEqPredicate('a', 1)
    b2 = jc.PathEqPredicate('b', 2)
    disjunction = jc.OR([a1, b2])
    expect = jc.CompositePredicateResult(
        valid=False, pred=disjunction,
        results=[a1(_LETTER_DICT), b2(_LETTER_DICT)])

    result = disjunction(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)

  def test_not_success(self):
    a1 = jc.PathEqPredicate('a', '1')
    not_a1 = jc.NOT(a1)

    expect = jc.CompositePredicateResult(
        valid=True, pred=not_a1, results=[a1(_LETTER_DICT)])
    result = not_a1(_LETTER_DICT)
    self.assertTrue(result)
    self.assertEqual(expect, result)

    b2 = jc.PathEqPredicate('b', '2')
    b2_or_a1 = jc.OR([b2, a1])
    not_b2_or_a1 = jc.NOT(b2_or_a1)
    expect = jc.CompositePredicateResult(
        valid=True, pred=not_b2_or_a1, results=[b2_or_a1(_LETTER_DICT)])
    result = not_b2_or_a1(_LETTER_DICT)
    self.assertTrue(result)
    self.assertEqual(expect, result)
    
  def test_not_fail(self):
    aA = jc.PathEqPredicate('a', 'A')
    not_aA = jc.NOT(aA)

    expect = jc.CompositePredicateResult(
        valid=False, pred=not_aA, results=[aA(_LETTER_DICT)])
    result = not_aA(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)

    bB = jc.PathEqPredicate('b', 'B')
    bB_or_aA = jc.OR([bB, aA])
    not_bB_or_aA = jc.NOT(bB_or_aA)
    expect = jc.CompositePredicateResult(
        valid=False, pred=not_bB_or_aA, results=[bB_or_aA(_LETTER_DICT)])
    result = not_bB_or_aA(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)
    
  def test_condition_success(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    ifAthenB = jc.IF(aA, bB)
    demorgan = jc.OR([jc.NOT(aA), bB])

    test_cases = [_LETTER_DICT, {'a':'X', 'b':'Y'}, {'a':'X', 'b':'B'}]
    for test in test_cases:
      expect = demorgan(test)
      result = ifAthenB(test)
      self.assertTrue(result)
      self.assertEqual(expect, result)
    
  def test_condition_fail(self):
    aA = jc.PathEqPredicate('a', 'A')
    b2 = jc.PathEqPredicate('b', '2')
    ifAthen2 = jc.IF(aA, b2)
    demorgan = jc.OR([jc.NOT(aA), b2])

    expect = demorgan(_LETTER_DICT)
    result = ifAthen2(_LETTER_DICT)
    self.assertFalse(result)
    self.assertEqual(expect, result)

  def test_condition_else_success(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    cC = jc.PathEqPredicate('c', 'C')

    aA_and_bB = jc.AND([aA, bB])
    impl_pred = jc.OR([aA_and_bB, cC])
    ifAthenBelseC = jc.IF(aA, bB, cC)

    # True if all conditions are true.
    # True if "if" satisfied and "then" matches.
    # True if only else condition is true.
    test_cases = [_LETTER_DICT,
                  {'a':'A', 'b':'B', 'c':'X'},
                  {'a':'X', 'b':'B', 'c':'C'},
                  {'a':'X', 'b':'X', 'c':'C'}]

    for i in range(3):
      test = test_cases[i]
      tried = [aA(test)]
      if i < 2:
        # First two have true IF to just execute THEN
        tried.append(bB(test))
      else:
        # Remainder have false IF to just execute ELSE
        tried.append(cC(test))

      expect = jc.CompositePredicateResult(
        valid=True, pred=ifAthenBelseC, results=tried)
      result = ifAthenBelseC(test)
      self.assertTrue(result)
      self.assertEqual(expect, result)

  def test_condition_else_fail(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')
    cC = jc.PathEqPredicate('c', 'C')

    ifAthenBelseC = jc.IF(aA, bB, cC)

    # False if all conditions are false
    # False if "if" is true and "then" is false even if "else" matches.
    test_cases = [{'a':'A', 'b':'X', 'c':'C'},
                  {'a':'X', 'b':'B', 'c':'D'}]
    for i in range(2):
      test = test_cases[i]
      tried = [aA(test)]
      if i < 1:
        # First has true IF so tries THEN
        tried.append(bB(test))
      else:
        # Remainder has false IF so tries ELSE
        tried.append(cC(test))

      expect = jc.CompositePredicateResult(
        valid=False, pred=ifAthenBelseC, results=tried)
      result = ifAthenBelseC(test)
      self.assertFalse(result)
      self.assertEqual(expect, result)
    

if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(LogicPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
