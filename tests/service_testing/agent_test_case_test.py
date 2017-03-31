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

from argparse import ArgumentParser
import unittest

import citest.service_testing.agent_test_case as agent_test_case
import citest.service_testing as st
import citest.json_contract as jc

from citest.base import (ExecutionContext, ConfigurationBindingsBuilder)
from fake_agent import (
    FakeAgent,
    FakeOperation,
    FakeStatus)


class FakeObserver(jc.ObjectObserver):
  def collect_observation(self, context, observation, trace=True):
    pass


class FakeVerifier(jc.ObservationVerifier):
  def __init__(self, valid):
    super(FakeVerifier, self).__init__('TestVerifier')
    self.__valid = valid

  def __call__(self, context, observation):
    return jc.ObservationVerifyResult(
        valid=self.__valid, observation=observation,
        good_results=[], bad_results=[], failed_constraints=[])


class AgentTestCaseTest(st.AgentTestCase):
  def setUp(self):
    self.testing_agent = FakeAgent()

  def test_pass(self):
    pass

  def test_raise_final_status_not_ok(self):
    attempt = agent_test_case.OperationContractExecutionAttempt('TestOp')
    operation = st.AgentOperation('TestStatus', agent=self.testing_agent)
    status = FakeStatus(operation)
    self.assertRaises(
        AssertionError,
        self.raise_final_status_not_ok, status, attempt)

  def test_assertContract_ok(self):
    context = ExecutionContext()
    verifier = FakeVerifier(True)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)
    self.assertContract(context, contract)

  def test_assertContract_failed(self):
    context = ExecutionContext()
    verifier = FakeVerifier(False)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)
    self.assertRaises(AssertionError, self.assertContract, context, contract)

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

  def _do_run_test_case(self, succeed, with_callbacks, with_context):
    # pylint: disable=unused-argument
    operation = FakeOperation('TestOperation', self.testing_agent)

    verifier = FakeVerifier(succeed)
    clause = jc.ContractClause(
        'TestClause', observer=FakeObserver(), verifier=verifier)
    contract = jc.Contract()
    contract.add_clause(clause)

    class HelperClass(object):
      """Need to share state between these helper methods and outer scope.

      This class provides the functions we are going to inject, along
      with state we can check in the outer scope.
      """
      cleanup_calls = 0
      execution_context = ExecutionContext() if with_context else None

      @staticmethod
      def status_extractor(status, context):
        if with_context:
          # Verify this is the context we injected.
          self.assertEquals(HelperClass.execution_context, context)
        self.assertIsNotNone(context.get('OperationStatus', None))
        self.assertIsNone(context.get('GOT_STATUS', None))
        context['GOT_STATUS'] = status

      @staticmethod
      def cleanup(context):
        self.assertIsNotNone(context.get('OperationStatus', None))
        self.assertEquals(context.get('OperationStatus', None),
                          context.get('GOT_STATUS', None))
        HelperClass.cleanup_calls += 1

    status_extractor = HelperClass.status_extractor
    cleanup = HelperClass.cleanup

    operation_contract = st.OperationContract(
        operation, contract, status_extractor=status_extractor, cleanup=cleanup)
    if succeed:
      self.run_test_case(
          operation_contract, context=HelperClass.execution_context)
    else:
      self.assertRaises(
          AssertionError,
          self.run_test_case,
          operation_contract, context=HelperClass.execution_context)
    self.assertEquals(1, HelperClass.cleanup_calls)

  def test_run_test_simple_ok(self):
    self._do_run_test_case(
        succeed=True, with_callbacks=False, with_context=False)

  def test_run_test_simple_fail(self):
    self._do_run_test_case(
        succeed=False, with_callbacks=False, with_context=False)

  def test_run_test_with_context_ok(self):
    self._do_run_test_case(
        succeed=True, with_callbacks=False, with_context=True)

  def test_run_test_with_context_fail(self):
    self._do_run_test_case(
        succeed=False, with_callbacks=False, with_context=True)

  def test_run_test_with_callbacks_ok(self):
    self._do_run_test_case(
        succeed=True, with_callbacks=True, with_context=False)

  def test_run_test_with_callbacks_fail(self):
    self._do_run_test_case(
        succeed=False, with_callbacks=True, with_context=False)


class TestScenario(st.AgentTestScenario):
  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    super(TestScenario, cls).initArgumentParser(parser, defaults=defaults)
    cls.iap_calls.append((parser, defaults))

  @classmethod
  def init_bindings_builder(cls, builder, defaults=None):
    super(TestScenario, cls).init_bindings_builder(
        builder, defaults=defaults)
    cls.ibb_calls.append((builder, defaults))


class AgentTestScenarioTest(unittest.TestCase):
  def test_init_argument_parser(self):
    parser = ArgumentParser()
    defaults = {'a': 'A'}

    class ArgParserScenario(TestScenario):
      iap_calls = []
      ibb_calls = []

    with self.assertRaises(NotImplementedError):
      ArgParserScenario.initArgumentParser(parser, defaults=defaults)
    self.assertEquals([], ArgParserScenario.iap_calls)
    self.assertEquals([], ArgParserScenario.ibb_calls)

  def test_init_bindings_builder(self):
    builder = ConfigurationBindingsBuilder()
    defaults = {'a': 'A'}

    class BindingsBuilderScenario(TestScenario):
      iap_calls = []
      ibb_calls = []

    BindingsBuilderScenario.init_bindings_builder(builder, defaults=defaults)
    self.assertEquals(1, len(BindingsBuilderScenario.iap_calls))
    self.assertEquals(builder, BindingsBuilderScenario.iap_calls[0][0])

    self.assertEquals(1, len(BindingsBuilderScenario.ibb_calls))
    self.assertEquals(builder, BindingsBuilderScenario.ibb_calls[0][0])
    

if __name__ == '__main__':
  unittest.main()
