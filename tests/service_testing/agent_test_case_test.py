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
# pylint: disable=invalid-name

import unittest

import citest.service_testing.agent_test_case as agent_test_case
import citest.service_testing as st
import citest.json_contract as jc


from .fake_agent import (
    FakeAgent,
    FakeOperation,
    FakeStatus)


class FakeObserver(jc.ObjectObserver):
  def collect_observation(self, observation, trace=True):
    pass


class FakeVerifier(jc.ObservationVerifier):
  def __init__(self, valid):
    super(FakeVerifier, self).__init__('TestVerifier')
    self.__valid = valid

  def __call__(self, observation):
    return jc.ObservationVerifyResult(
        valid=self.__valid, observation=observation,
        good_results=[], bad_results=[], failed_constraints=[])


class AgentTestCaseTest(st.AgentTestCase):
  def setUp(self):
    self.testing_agent = FakeAgent()

  def test_raise_final_status_not_ok(self):
    attempt = agent_test_case.OperationContractExecutionAttempt('TestOp')
    operation = st.AgentOperation('TestStatus', agent=self.testing_agent)
    status = FakeStatus(operation)
    self.assertRaises(
        AssertionError,
        self.raise_final_status_not_ok, status, attempt)

  def test_assertContract_ok(self):
    verifier = FakeVerifier(True)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)
    self.assertContract(contract)

  def test_assertContract_failed(self):
    verifier = FakeVerifier(False)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)
    self.assertRaises(AssertionError, self.assertContract, contract)

  def test_assertVerifyResults_ok(self):
    observation = jc.Observation()
    verify_results = jc.ObservationVerifyResult(
        valid=True, observation=observation,
        good_results=[], bad_results=[], failed_constraints=[])
    self.assertVerifyResults(verify_results)

  def test_assertVerifyResults_failed(self):
    observation = jc.Observation()
    verify_results = jc.ObservationVerifyResult(
        valid=False, observation=observation,
        good_results=[], bad_results=[], failed_constraints=[])
    self.assertRaises(AssertionError, self.assertVerifyResults, verify_results)

  def test_run_test_case_ok(self):
    operation = FakeOperation('TestOperation', self.testing_agent)

    verifier = FakeVerifier(True)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    operation_contract = st.OperationContract(operation, contract)
    self.run_test_case(operation_contract)

  def test_run_test_case_failed(self):
    operation = FakeOperation('TestOperation', self.testing_agent)

    verifier = FakeVerifier(False)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    operation_contract = st.OperationContract(operation, contract)
    self.assertRaises(AssertionError, self.run_test_case, operation_contract)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(AgentTestCaseTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
