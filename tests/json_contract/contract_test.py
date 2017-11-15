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
# pylint: disable=invalid-name

import unittest

from citest.base import (
  ExecutionContext,
  JsonSnapshotHelper)

import citest.json_contract as jc
import citest.json_predicate as jp

_LETTER_ARRAY = ['a', 'b', 'c']
_NUMBER_ARRAY = [1, 2, 3]

_LETTER_DICT = {'a':'A', 'b':'B', 'z':'Z'}
_NUMBER_DICT = {'a':1, 'b':2, 'three':3}
_MIXED_DICT = {'a':'A', 'b':2, 'x':'X'}
_COMPOSITE_DICT = {'letters': _LETTER_DICT, 'numbers': _NUMBER_DICT}


class FakeObserver(jc.ObjectObserver):
  def __init__(self, fake_observation):
    super(FakeObserver, self).__init__()
    self.__fake_observation = fake_observation


  def collect_observation(self, context, observation):
    observation.extend(self.__fake_observation)
    return observation.objects


class JsonContractTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0!r}\nGOT\n{1!r}'.format(expect, have)
    JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)

  def test_clause_success(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('B')
    observation.add_object('A')
    fake_observer = FakeObserver(observation)

    eq_A = jp.LIST_MATCHES([jp.STR_EQ('A')])
    verifier = jc.ValueObservationVerifierBuilder('Has A').EXPECT(eq_A).build()

    clause = jc.ContractClause('TestClause', fake_observer, verifier)

    expect_result = jc.contract.ContractClauseVerifyResult(
        True, clause, verifier(context, observation))
    result = clause.verify(context)
    self.assertEqual(expect_result, result)
    self.assertTrue(result)

  def test_clause_failure(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('B')
    fake_observer = FakeObserver(observation)

    eq_A = jp.LIST_MATCHES([jp.STR_EQ('A')])
    verifier = jc.ValueObservationVerifierBuilder('Has A').EXPECT(eq_A).build()

    clause = jc.ContractClause('TestClause', fake_observer, verifier)

    expect_result = jc.contract.ContractClauseVerifyResult(
        False, clause, verifier(context, observation))
    result = clause.verify(context)
    self.assertEqual(expect_result, result)
    self.assertFalse(result)

  def test_contract_success(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')
    fake_observer = FakeObserver(observation)

    eq_A = jp.LIST_MATCHES([jp.STR_EQ('A')])
    verifier = jc.ValueObservationVerifierBuilder('Has A').EXPECT(eq_A).build()

    clause = jc.ContractClause('TestClause', fake_observer, verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    expect_result = jc.contract.ContractVerifyResult(
        True, [clause.verify(context)])

    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertTrue(result)

  def test_contract_failure(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('B')
    fake_observer = FakeObserver(observation)

    eq_A = jp.LIST_MATCHES([jp.STR_EQ('A')])
    verifier = jc.ValueObservationVerifierBuilder('Has A').EXPECT(eq_A).build()

    clause = jc.ContractClause('TestClause', fake_observer, verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    expect_result = jc.contract.ContractVerifyResult(
        False, [clause.verify(context)])

    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertFalse(result)

  def test_contract_mixed_object_failure_ok(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')
    observation.add_object('B')
    fake_observer = FakeObserver(observation)

    eq_A = jp.LIST_MATCHES([jp.STR_EQ('A')])
    verifier = jc.ValueObservationVerifierBuilder('Has A').EXPECT(eq_A).build()

    clause = jc.ContractClause('TestClause', fake_observer, verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    expect_result = jc.contract.ContractVerifyResult(
        True, [clause.verify(context)])

    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertTrue(result)

  def test_contract_mixed_clause_failure_not_ok(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')
    fake_observer = FakeObserver(observation)

    verifier = (jc.ValueObservationVerifierBuilder('Has A and B')
                .contains_match([jp.STR_EQ('A'), jp.STR_EQ('B')])
                .build())

    clause = jc.ContractClause('TestClause', fake_observer, verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    expect_result = jc.contract.ContractVerifyResult(
        False, [clause.verify(context)])

    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertFalse(result)

  def mixed_exclude_helper(self, strict):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')
    observation.add_object('B')
    observation.add_object('C')
    fake_observer = FakeObserver(observation)

    # We dont expect to see B in the list.
    # This can be interpreted two ways -- strictly or not strictly.
    # Strictly means no results should ever contain B.
    # Non strict means some result should not contain B.
    builder = jc.ValueObservationVerifierBuilder(
        'Test Excludes', strict=strict)
    builder.excludes_path_value(None, 'B')

    clause = jc.ContractClause('TestClause', fake_observer, builder.build())
    contract = jc.Contract()
    contract.add_clause(clause)

    # Doesnt matter whether strict or not since this is checking cardinality
    # over the entire list via the excludes clause.
    expect_result = jc.contract.ContractVerifyResult(
        False, [clause.verify(context)])
    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertEqual(False, result.valid)

  def test_contract_mixed_exclude_strict_not_ok(self):
    self.mixed_exclude_helper(strict=True)

  def test_contract_mixed_exclude_not_strict_ok(self):
    self.mixed_exclude_helper(strict=False)

  def test_multiple_required(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')
    observation.add_object('B')
    observation.add_object('C')
    fake_observer = FakeObserver(observation)

    eq_A_or_B = jp.OR([jp.STR_EQ('A'), jp.STR_EQ('B')])
    builder = jc.ValueObservationVerifierBuilder('Test Multiple')
    builder.contains_path_pred(None, eq_A_or_B, min=2)

    clause = jc.ContractClause('TestClause', fake_observer, builder.build())
    contract = jc.Contract()
    contract.add_clause(clause)

    expect_result = jc.contract.ContractVerifyResult(
        True, [clause.verify(context)])
    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertEqual(True, result.valid)

  def test_contract_observation_failure(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_error(
        jp.PredicateResult(False, comment='Observer Failed'))
    fake_observer = FakeObserver(observation)

    eq_A = jp.LIST_MATCHES([jp.STR_EQ('A')])
    verifier = jc.ValueObservationVerifierBuilder('Has A').EXPECT(eq_A).build()

    clause = jc.ContractClause('TestClause', fake_observer, verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    expect_result = jc.contract.ContractVerifyResult(
        False, [clause.verify(context)])

    result = contract.verify(context)
    self.assertEqual(expect_result, result)
    self.assertFalse(result)


  def _try_verify(self, context, contract, observation,
                  expect_ok, expect_results=None, dump=False):
    """Helper function for a verifier result on a given observation.

    Args:
      contract: The jc.Contract to verify.
      observation: The jc.Observa
      expect_ok: Whether we expect the contract to succeed or not.
      expect_results: If not None, then the expected ContractVerifyResult.
      dump: If True then print the expect_results to facilitate debugging.
    """
    verify_results = contract.verify(context)
    ok = verify_results.__nonzero__()

    error_msg = '{expect_ok} != {ok}\n{failures}'.format(
        expect_ok=expect_ok, ok=ok,
        failures=verify_results.enumerated_summary_message)
    if dump:
      print 'VERIFY_RESULTS: {0}\n'.format(verify_results)
      print '\nEXPECT: {0}\n'.format(expect_results)
      print 'OBSERVATION: {0}\n'.format(verify_results.observation)

    self.assertEquals(expect_ok, ok, error_msg)
    if expect_results:
      self.assertEquals(
          expect_results, verify_results,
          'EXPECT\n{0}\n\nACTUAL\n{1}'.format(
              expect_results, verify_results))


if __name__ == '__main__':
  unittest.main()
