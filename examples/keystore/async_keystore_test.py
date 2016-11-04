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

import citest.base
from citest.service_testing import http_agent
import citest.service_testing as st

from keystore_test_scenario import KeystoreTestScenario


class KeystoreStatus(st.HttpOperationStatus):
  """Adapts our KeystoreServer's async prototocol to citest OperationStatus.

  The application protocol for our server's asynchronous operations is that
  the original request returns a string containing a task identifier.
  The server has a /status/{id} URL that we can query for that status.
  The queried status is a simple string identifying the state.
  WAITING, RUNNING, DONE (success) or ERROR (failure) where ERROR has
  additional explanation.
  """

  @property
  def finished(self):
    """Implements OperationStatus API.

    Indicates whether our asynchronous task has completed or not.
    """
    return self.__current_state in ['DONE', 'ERROR']

  @property
  def finished_ok(self):
    """Implements OperationStatus API.

    Indicates whether we finished successfully or not.
    """
    return self.__current_state == 'DONE'

  @property
  def error(self):
    """Implements OperationStatus API.

    Indicates whether we finished with a failure, and what the failure was.
    """
    return self.__error

  @property
  def id(self):
    """The id for this status result."""
    return self.__task_id

  @property
  def detail_path(self):
    """The URL to query for the current task status."""
    return self.__detail_path

  @property
  def current_state(self):
    """A custom method to access our current task state."""
    return self.__current_state

  def __init__(self, operation, original_response=None):
    """Constructor.

    Args:
      operation: [AgentOperation] The operation instance this is for.
      original_response: [HttpResponseType] The response from the operation.
    """
    super(KeystoreStatus, self).__init__(operation, original_response)
    self.__task_id = original_response.output
    self.__current_state = None  # Last known state (after last refresh()).
    self.__detail_path = '/status/{id}'.format(id=self.__task_id)
    self.__error = None

  def __str__(self):
    return 'id={id} current_state={current_state} error={error}'.format(
        id=self.__task_id, current_state=self.current_state,
        error=self.__error)

  def refresh(self, **kwargs):
    """Implements HttpOperationStatus interface.

    Refreshes the status state by polling the underlying server.
    """
    http_response = self.agent.get(self.detail_path)
    self.set_http_response(http_response)

  def set_http_response(self, http_response):
    """Implements HttpOperationStatus interface.

    Args:
      http_response: [HttpResponseType] A response from a status poll.
    Updates our state from a HTTP response
    """
    super(KeystoreStatus, self).set_http_response(http_response)
    if http_response.http_code is None:
      self.__current_state = 'Unknown'
      return

    parts = http_response.output.split(' ', 1)
    self.__current_state = parts[0]
    self.__error = parts[1] if len(parts) > 1 else None


class AsynchronousKeystoreTest(st.AgentTestCase):
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
    AsynchronousKeystoreTest.__get_scenario()

  @staticmethod
  def tearDownClass():
    """Implements unittest.TestCase setUpClass to terminate our server."""
    AsynchronousKeystoreTest.__get_scenario().cleanup()

  @property
  def scenario(self):
    """Returns a shared scenario used across all the tests."""
    return AsynchronousKeystoreTest.__get_scenario()

  def make_key(self, name):
    """Helper function that creates keys specific to this invocation."""
    return self.scenario.make_key(name)

  def test_a_put_string_eventual_correctness(self):
    """Example writes a value that is not immediately observable.

    The request itself is synchronous, but the server does not make
    the value immediately available so observer may need to retry.
    """
    key = self.make_key('MyEventualCorrectnessKey')
    expect_value = 'My Eventual-Correctness Value'

    # Our server is really going to use an asynchronous protocol,
    # but this test is ignoring that and treating the put at face value.
    # It will attempt to observe a few times until eventually it sees what
    # we were expecting to eventually see.
    operation = http_agent.HttpPostOperation(
        title='Writing Key Value',
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key + '?async')
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value', retryable_for_secs=3)
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', expect_value))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test)

  def test_b_put_string_with_async_request(self):
    """Example writes a string value asynchronously then checks for it.

    The request is asynchronous so its final status is not immediately known.
    We'll inform citest of the application protocol so it can wait for the
    request to complete, then observe the results.
    """
    key = self.make_key('MyAsyncKey')
    expect_value = 'My Async Value'

    operation = http_agent.HttpPostOperation(
        title='Writing Key Value Asynchronously',
        status_class=KeystoreStatus,
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key + '?async&delay=1.5')

    # For our server, we expect that the observer will be able to see
    # the value immediately once the operation finishes even though the
    # operation itself will take 1.5 seconds to complete (after the original
    # HTTP POST operation completes).
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', expect_value))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test)

  def test_c_put_string_with_async_request_timeout_ok(self):
    """Example writes a string value asynchronously then checks for it.

    The request is asynchronous so its final status is not immediately known.
    We'll inform citest of the application protocol so it can wait for the
    request to complete, then observe the results.
    """
    key = self.make_key('MyTimeoutKey')
    expect_value = 'My Timeout Value'

    operation = http_agent.HttpPostOperation(
        title='Writing Key Value Asynchronously',
        status_class=KeystoreStatus,
        data=json.JSONEncoder().encode(expect_value),
        path='/put/' + key + '?async&delay=2.5',
        max_wait_secs=2)

    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Check Key Value', retryable_for_secs=1)
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', expect_value))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    self.run_test_case(test, timeout_ok=True)

  def test_m_delayed_operation_failure(self):
    """Example showing an asynchronous operation failure."""
    context = citest.base.ExecutionContext()
    key = self.make_key('InvalidKey')
    expect_value = 'Unexpected Value'

    operation = http_agent.HttpDeleteOperation(
        title='Delayed 404',
        status_class=KeystoreStatus,
        data=json.JSONEncoder().encode(expect_value),
        path='/delete/' + key + '?async&delay=1')
    builder = st.HttpContractBuilder(self.scenario.agent)
    (builder.new_clause_builder('Never Checks For Value')
     .get_url_path('/lookup/' + key)
     .contains_path_eq('', expect_value))
    contract = builder.build()

    test = st.OperationContract(operation, contract)
    with self.assertRaises(AssertionError):
      self.run_test_case(test, context=context)

    # citest wrote into the context the 'OperationStatus'
    # Normally this is so we can write predicates that look into it
    # using lambda expressions for defered bindings. In this case we'll
    # look at it to show that the status we got back had the delayed error we
    # anticipated in it.
    status = context['OperationStatus']
    self.assertEqual('ERROR', status.current_state)
    self.assertEqual('KeyError', status.error.split(' ', 1)[0])


def main():
  """Runs the tests."""
  defaults = {
      'TEST_ID':
          'MySimpleTest-' + KeystoreTestScenario.DEFAULT_TEST_ID
      }

  return citest.base.TestRunner.main(
      default_binding_overrides=defaults,
      test_case_list=[AsynchronousKeystoreTest])


if __name__ == '__main__':
  sys.exit(main())
