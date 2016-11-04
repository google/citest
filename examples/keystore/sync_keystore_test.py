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


"""Illustrates some citest examples against a simple HTTP web server.

These examples happen to use the same agent to both send operations and
make observations but they are independent of one another.

Usage is
   python examples/keystore/sync_keystore_test [--host HOST] [--port PORT]

If a HOST and PORT are provided then they keystore must already be running
at that location, otherwise the test will temporarily fork one on an unused
port.

When the test completes, it will write out an HTML file containing the
reporting analysis. This is the most useful way to see what happened.
Otherwise the log files can be consulted for details.
"""
# pylint: disable=no-name-in-module
# pylint: disable=no-member
# pylint: disable=import-error
# pylint: disable=invalid-name

import json
import sys
from unittest import expectedFailure

import citest.base
from citest.service_testing import http_agent
import citest.json_predicate as jp
import citest.service_testing as st

from keystore_test_scenario import KeystoreTestScenario


class SynchronousKeystoreTest(st.AgentTestCase):
  """Different test examples."""

  @staticmethod
  def __get_scenario():
    """Helper method to get a scenario.

    Normally this would be the implementation of the scenario() property.
    However since we're going to use the scenario in our setUpClass and
    tearDownClass in order to fork the server, we're creating this helper.
    """
    return citest.base.TestRunner.global_runner().get_shared_data(
        KeystoreTestScenario)

  @staticmethod
  def setUpClass():
    """Implements unittest.TestCase setUpClass to fork our server."""
    # The scenario forks the server as a side effect of being created.
    SynchronousKeystoreTest.__get_scenario()

  @staticmethod
  def tearDownClass():
    """Implements unittest.TestCase setUpClass to terminate our server."""
    SynchronousKeystoreTest.__get_scenario().cleanup()

  @property
  def scenario(self):
    """Returns a shared scenario used across all the tests."""
    return SynchronousKeystoreTest.__get_scenario()

  def make_key(self, name):
    """Helper function that creates keys specific to this invocation."""
    return self.scenario.make_key(name)

  def test_a_put_string(self):
    """Example writes a string value then checks for it."""
    key = self.make_key('MyStringKey')
    expect_value = 'My Key Value'

    operation = http_agent.HttpPostOperation(
        title='Writing Key Value',
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key)
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', expect_value))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test)

  def test_b_put_dict(self):
    """Example writes a dict value then checks for parts of it."""
    key = self.make_key('MyDictKey')
    expect_value = {'a': 'A', 'b': 'B', 'c': 'C'}

    operation = http_agent.HttpPostOperation(
        title='Writing Key Value',
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key)
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value')
     .get_url_path('/lookup/' + key)
     .contains_match({'a': jp.EQUIVALENT('A'),
                      'b': jp.EQUIVALENT('B')}))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test)

  def test_c_put_array(self):
    """Example writes an array value then shows many ways to check values."""
    key = self.make_key('MyArrayKey')
    expect_value = [{'a': 1, 'b': 1}, 2, {'a': 3, 'b': 3}]

    operation = http_agent.HttpPostOperation(
        title='Writing Key Value',
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key)
    # Examples of different ways to express things
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Contains a=1 and contains b=3')
     .get_url_path('/lookup/' + key)
     .contains_path_value('a', 1)
     .contains_path_value('b', 3))
    (builder.new_clause_builder('Contains (a=1 and b=1))')
     .get_url_path('/lookup/' + key)
     .contains_pred_list([jp.PathPredicate('a', jp.NUM_EQ(1)),
                          jp.PathPredicate('b', jp.NUM_EQ(1))]))
    (builder.new_clause_builder('Does not contain (a=1 and b=3)')
     .get_url_path('/lookup/' + key)
     .excludes_pred_list([jp.PathPredicate('a', jp.NUM_EQ(1)),
                          jp.PathPredicate('b', jp.NUM_EQ(3))]))
    (builder.new_clause_builder('Contains List')
     .get_url_path('/lookup/' + key)
     .contains_match([jp.EQUIVALENT(2),
                      jp.DICT_MATCHES({'a': jp.EQUIVALENT(3),
                                       'b': jp.DIFFERENT(1)})]))
    (builder.new_clause_builder("Contains Multiple A's >= 0")
     .get_url_path('/lookup/' + key)
     .contains_path_pred('a', jp.NUM_GE(0), min=2))
    (builder.new_clause_builder("Contains only 1 A >= 2")
     .get_url_path('/lookup/' + key)
     .contains_path_pred('a', jp.NUM_GE(2), min=1, max=1))
    (builder.new_clause_builder("Contains no A >= 10")
     .get_url_path('/lookup/' + key)
     .excludes_path_pred('a', jp.NUM_GE(10)))

    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test)

  def test_d_use_context_for_unknown_value(self):
    """Example uses dynamic return result from operation to check value."""
    key = self.make_key('MyRandomKey')
    operation = http_agent.HttpPostOperation(
        title='Generating Key Value',
        data=json.JSONEncoder().encode(''),
        path='/put_random/' + key)
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', lambda context: context['EXPECT']))
    contract = builder.build()

    def extractor(operation_status, context):
      """Helper function that populates context with value from status.

      This is so we can write our contract in terms of a value not known
      until we perform the actual operation.
      """
      response = operation_status.raw_http_response
      context.set_snapshotable('EXPECT', response.output)

    test = st.OperationContract(operation, contract,
                                status_extractor=extractor)
    self.run_test_case(test)

  def test_j_just_observe(self):
    """Example checks a contract without an operation."""
    key = self.make_key('MyDictKey')
    context = citest.base.ExecutionContext()

    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('a', 'A'))
    contract = builder.build()
    results = contract.verify(context)
    self.assertTrue(results)

  def test_k_expect_observe_error(self):
    """Example expects the observation itself to fail."""
    key = self.make_key('InvalidKey')
    context = citest.base.ExecutionContext()

    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Expect Not Found Error')
     .get_url_path('/lookup/' + key)
     .append_verifier(
         st.HttpObservationFailureVerifier('Expect 404', 404)))
    contract = builder.build()
    results = contract.verify(context)
    self.assertTrue(results)

  def test_l_unexpected_observe_error(self):
    """Example showing what happens when a contract fails."""
    key = self.make_key('InvalidKey')
    context = citest.base.ExecutionContext()

    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Expect Not Found Error')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('a', 'A'))
    contract = builder.build()
    results = contract.verify(context)
    self.assertFalse(results)

  @expectedFailure
  def test_m_failure(self):
    """Example showing a typical test failure."""
    key = self.make_key('MyRandomKey')
    expect_value = 'My Key Value'

    operation = http_agent.HttpPostOperation(
        title='Writing Key Value',
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key)
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check For Wrong Value')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', 'Not ' + expect_value))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test)


def main():
  """Runs the tests."""
  defaults = {
      'TEST_ID':
          'MySimpleTest-' + KeystoreTestScenario.DEFAULT_TEST_ID
  }

  return citest.base.TestRunner.main(
      default_binding_overrides=defaults,
      test_case_list=[SynchronousKeystoreTest])


if __name__ == '__main__':
  sys.exit(main())
