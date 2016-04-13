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


"""Specialization of base.BaseTestCase for testing with citest.BaseAgents.

An AgentTestCase talks to both a BaseAgent and an external
observer, it then uses data from the external observer to verify expectations
made while talking to the TestableSystem.

The actual tests are written using operation_contract.OperationContract.
Each OperationContract contains an AgentOperation, which is sent to the
BaseAgent, and a Contract which specifies the expected system state
(resources it expects to find and/or resources it does not expect to find).

A detailed log file is written as the test runs for more information.
The default log file name is the name of the python module,
but can be changed with --log_filename and --log_dir.
"""


# Standard python modules.
from multiprocessing.pool import ThreadPool
import time
import traceback

# Our modules.
from ..base import args_util
from ..base import BaseTestCase
from ..base import JournalLogger
from ..base import JsonSnapshotable
from .scenario_test_runner import ScenarioTestRunner


_DEFAULT_TEST_ID = time.strftime('%H%M%S')


# Number of decimals to round time durations.
_DURATION_PRECISION = 3  # millis


class OperationContractExecutionAttempt(JsonSnapshotable):
  """Represents an individual attempt at running an OperationContract test case.

  This class captures the attempt and results so that it can be recorded in
  a snapshot.
  """

  @property
  def completed(self):
    return self.__stop is not None

  @property
  def default_relation(self):
    """The default relation to assume when snapshotting.

    For more information on the use of the default_relation snapshotting
    annotation, see base/snapshot.py SnapshotEntity.

    In practice this attempt is one of many in a list. The default_relation
    permits different elements to distinguish valid/invalid relationships.
    """
    if self.__exception is not None:
      return 'ERROR'
    elif self.__verification is not None:
      return 'VALID' if self.__verification else 'INVALID'
    else:
      return None

  def __init__(self, name):
    """Constructor.

    Args:
      name: [string] The name of the operation is only used for reporting.
    """
    self.__start = time.time()
    self.__stop = None
    self.__name = name
    self.__verification = None
    self.__verification_summary = None
    self.__status = None
    self.__status_summary = None
    self.__exception = None
    self.__traceback = None

  def set_exception(self, exception, traceback=None):
    self.__stop = time.time()
    self.__exception = exception
    self.__traceback = traceback

  def set_status(self, status, summary=""):
    """Sets the final status of the operation.

    Args:
      status: [AgentOperationStatus] The citest status from the operation.
      summary: [string] An optional summary of the status for reporting.
    """
    self.__stop = time.time()
    self.__status = status
    self.__status_summary = summary

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    default_relation = self.default_relation
    if default_relation  is not None:
      entity.add_metadata('_default_relation', default_relation)

    entity.add_metadata('_timestamp', self.__start)
    if self.__status_summary:
      entity.add_metadata('summary', self.__status_summary)
    builder.make(entity, 'Name', self.__name)
    builder.make(entity, 'Duration',
                 round(self.__stop - self.__start, _DURATION_PRECISION))

    if self.__status is not None:
      edge = builder.make(entity, 'OperationStatus', self.__status)
      if self.__status.finished:
        edge.add_metadata(
            'relation',
            builder.determine_valid_relation(self.__status.finished_ok))

    if self.__exception is not None:
      builder.make_error(entity, 'Exception', self.__exception)
      if self.__traceback is not None:
        builder.make_error(entity, 'ExceptionTrace', self.__traceback,
                           format="pre")

    if self.__verification:
      edge = builder.make(
          entity, 'Verification', self.__verification,
          relation=builder.determine_valid_relation(self.__verification))
      if self.__verification_summary:
        edge.add_metadata('summary', self.__verification_summary)


class OperationContractExecutionTrace(JsonSnapshotable):
  """Represents the execution and evaluation of an OperationContract test case.
  """

  def __init__(self, test_case):
    """Constructor."""
    self.__test_case = test_case
    self.__start = time.time()
    self.__end = None
    self.__verify_results = None
    self.__operation_end = None
    self.__operation_summary = None
    self.__exception = None
    self.__traceback = None
    self.__attempts = []

  def set_verify_results(self, verify_results):
    """Sets the verification results once they are known."""
    self.__end = time.time()
    self.__verify_results = verify_results

  def set_exception(self, ex, traceback=None):
    """Sets the exception if one was encountered."""
    self.__end = time.time()
    self.__traceback = traceback
    self.__exception = ex

  def set_operation_summary(self, summary):
    """Sets the summary for this execution trace, if one is known."""
    self.__operation_end = time.time()
    self.__operation_summary = summary

  def new_attempt(self):
    """Adds a new attempt record.

    The details of the attempt should be added into the result.

    Returns:
       OperationContractExecutionAttempt to update with attempt details.
    """
    attempt = OperationContractExecutionAttempt(len(self.__attempts))
    self.__attempts.append(attempt)
    return attempt

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    entity.add_metadata('_title', self.__test_case.operation.title)

    builder = snapshot.edge_builder
    builder.make(entity, 'Test Case', self.__test_case)

    my_default_relation = None
    if self.__exception is not None:
      my_default_relation = 'ERROR'
      builder.make_error(entity, 'Exception', self.__exception, format='pre')

    if self.__attempts:
      edge = builder.make(entity, 'Attempts', list(reversed(self.__attempts)))
      final_relation = self.__attempts[-1].default_relation
      if final_relation is not None:
        edge.add_metadata('relation', final_relation)
        entity.add_metadata('_default_relation', final_relation)

    if self.__verify_results is not None:
      verification_relation = builder.determine_valid_relation(
          self.__verify_results)
      my_default_relation = my_default_relation or verification_relation
      builder.make(
          entity, 'Verification', self.__verify_results,
          relation=verification_relation)

    entity.add_metadata('_default_relation', my_default_relation)
    builder.make(entity, 'TestDuration',
                 round(self.__end - self.__start, _DURATION_PRECISION))

    if self.__operation_end is not None:
      builder.make(entity, 'OperationDuration',
                   round(self.__operation_end - self.__start,
                         _DURATION_PRECISION))
      builder.make(entity, 'VerificationDuration',
                   round(self.__end - self.__operation_end,
                         _DURATION_PRECISION))


class AgentTestScenario(object):
  """Class for sharing scenario data and state across different test cases.

  This class does not really define much behavior. It just manages
  a set of parameters. The intent is for specialized classes to
  define the OperationTestCases, using the parameters to determine
  the final values to use.
  """

  DEFAULT_TEST_ID = _DEFAULT_TEST_ID

  @property
  def agent(self):
    """The primary BaseAgent that is the focal point for the test."""
    return self.__agent

  @property
  def bindings(self):
    """A dictionary used to bind configuration parameters for the test.

    Often these are somewhat arbitrary values that are used for multiple
    tests and might be desirable to control with command-line arguments
    when debugging or other develpment. The binding keys are all
    upper-case by convention for readability to make binding keys more
    distinct within the code.
    """
    return self.__bindings

  @staticmethod
  def make_scenario(scenario_class, bindings):
    """Factory method for instantiating this class with bindings."""
    return scenario_class(bindings)

  @property
  def test_id(self):
    """Returns a unique id string for identifying this test execution instance.

    This can be used to decorate external resources to help them trace
    back into this test execution.
    """
    return self.__test_id

  def __init__(self, bindings, agent=None):
    """Construct scenario

    Args:
      bindings: [dict] key/value configuration values.
          The keys are in upper case. The actual keys are not standardized,
          rather the scenarios may have a set of parameters that they use
          for their needs.

      agent: [BaseAgent] Primary agent used in this scenario.
          If not prodided then construct a new one with the class new_agent
          factory method.
    """
    self.__bindings = bindings
    self.__agent = agent or self.new_agent(bindings)
    self.__test_id = bindings.get('TEST_ID', _DEFAULT_TEST_ID)

  def substitute_variables(self, text):
    """Substitute $KEY with the bound value of KEY.

    Returns:
      Copy of text with bound variables substituted with their values.
    """
    return args_util.replace(text, self.__bindings)

  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    """Adds arguments introduced by the BaseTestCase module.

    Args:
      parser: [argparse.ArgumentParser] Instance to add to.
    """
    defaults = defaults or {}
    parser.add_argument(
        '--test_id', default=defaults.get('TEST_ID', _DEFAULT_TEST_ID),
        help='A short, [reasonably] unique identifier for this test')

  @classmethod
  def new_agent(cls, bindings):
    """Factory method to create the agent to pass into the constructor."""
    raise NotImplementedError(
        'new_agent not specialized on ' + cls.__name__)


class AgentTestCase(BaseTestCase):
  """Base class for agent integration tests."""

  @property
  def report_journal(self):
    """The Journal used for producing the test report."""
    return ScenarioTestRunner.global_runner().report_journal

  def report(self, obj):
    """Write the object state into the test report."""
    ScenarioTestRunner.global_runner().report(obj)

  @property
  def scenario(self):
    """Return the current test scenario instance."""
    return ScenarioTestRunner.global_runner().scenario

  @property
  def testing_agent(self):
    """The BaseAgent for the current test scenario's testable system."""
    return self.scenario.agent

  def assertContract(self, contract):
    """Verify the specified contract holds, raise and exception if not."""
    # pylint: disable=invalid-name
    verify_results = contract.verify()
    self.assertVerifyResults(verify_results)

  def assertVerifyResults(self, verify_results):
    """Assert that the results are valid.
    Args:
        verify_results: [ContractVerifyResults]
    Raises:
        AssertionError if not.
    """
    # pylint: disable=invalid-name
    self.assertTrue(
        verify_results,
        'Contract clauses failed:\n{summary}\n{detail}'.format(
            summary=verify_results.enumerated_summary_message,
            detail=str(verify_results)))

  def verifyFinalStatusOk(self, status, timeout_ok=False,
                          final_attempt=None, execution_trace=None):
    """Verify that an agent request completed successfully.

    This is used to verify the messaging with the agent completed as expected
    before observing whether the expected side effects have taken place.

    Args:
      status: [AgentOperationStatus] The operation status.
      timeout_ok: [bool] If True then a timeout status is acceptable.
      final_attempt: [OperationContractExecutionAttempt]
      execution_trace: [OperationContractExecutionTrace]

    Returns:
      True if final status is ok, otherwise false.
    """
    if status is None:
      error = 'Never received a final status.'
      final_attempt.set_exception(error)
      execution_trace.set_exception(error)
      return False

    # pylint: disable=invalid-name
    # This is not because we dont want there to be an "exception".
    # Rather, we want the unit test to directly report what they were.
    if status.exception_details:
      self.logger.info(
          'status has exception_details=%s', status.exception_details)

    if not status.finished:
      if timeout_ok:
        warning = 'Never completed, but timeouts are ok'
        final_attempt.set_exception(warning)
        execution_trace.set_exception(warning)
        self.logger.warning(
            'Request never completed [%s], but that is ok.',
            status.current_state)
        return True

    if status.timed_out:
      warning = 'Request timed out and never completed.'
      final_attempt.set_exception(warning)
      execution_trace.set_exception(warning)
      self.logger.warning(
          'WARNING: It appears the status has timed out. Continuing anyway.')
      return True

    if not status.finished_ok:
      final_attempt.set_exception('Did not finish OK.')
      execution_trace.set_exception('Did not finish OK.')
      return False

    return True

  def raiseFinalStatusNotOk(self, status, final_attempt):
    raise AssertionError('{0}\n{1}'.format(
        status.exception_details, str(status)))

  def run_test_case_list(
      self, test_case_list, max_concurrent, timeout_ok=False,
      max_retries=0, retry_interval_secs=5, full_trace=False):
    """Run a list of test cases.

    Args:
      test_case_list: [list of OperationContract] Specifies the tests to run.
      max_concurrent: [int] The number of cases that can be run concurrently.
      timeout_ok: [bool] If True then individual tests can timeout and still
         be considered having a successful AgentOperationStatus.
      max_retries: [int] Number of independent retries permitted on
         individual operations if the operation status fails. A value of 0
         indicates that a test should only be given a single attempt.
      retry_interval_secs: [int] Time between retries of individual operations.
      full_trace: [bool] If True then provide detailed execution tracing.
    """
    num_threads = min(max_concurrent, len(test_case_list))
    pool = ThreadPool(processes=num_threads)
    def run_one(test_case):
      """Helper function to run individual tests."""
      self.run_test_case(
          test_case=test_case, timeout_ok=timeout_ok,
          max_retries=max_retries, retry_interval_secs=retry_interval_secs,
          full_trace=full_trace)

    self.logger.info(
        'Running %d tests across %d threads.',
        len(test_case_list), num_threads)
    pool.map(run_one, test_case_list)
    self.logger.info('Finished %d tests.', len(test_case_list))

  def run_test_case(self, test_case, timeout_ok=False,
                    max_retries=0, retry_interval_secs=5, full_trace=False):
    """Run the specified test operation from start to finish.

    Args:
      test_case: [OperationContract] To test.
      timeout_ok: [bool] Whether an AgentOperationStatus timeout implies
          a test failure. If it is ok to timeout, then we'll still verify the
          contracts, but skip the final status check if there is no final
          status yet.
      max_retries: [int] Number of independent retries permitted on
          individual operations if the operation status fails. A value of 0
          indicates that a test should only be given a single attempt.
      retry_interval_secs: [int] The number of seconds to wait between retries.
      full_trace: [bool] If true, then apply as much tracing as possible, else
          use the default tracing. The intent here is to be able to crank up
          the tracing when needed but not be overwhelmed by data when the
          default tracing is typically sufficient.
    """
    self.log_start_test(test_case.title)
    if max_retries < 0:
      raise ValueError(
          'max_retries={max} cannot be negative'.format(max=max_retries))
    if retry_interval_secs < 0:
      raise ValueError(
          'retry_interval_secs={secs} cannot be negative'.format(
              secs=retry_interval_secs))

    execution_trace = OperationContractExecutionTrace(test_case)
    verify_results = None
    final_status_ok = None
    context_relation = None
    attempt_info = None
    try:
      JournalLogger.begin_context('Test "{0}"'.format(test_case.title))
      JournalLogger.delegate(
          "store", test_case.operation,
          _title='Operation "{0}" Specification'.format(
              test_case.operation.title))
      max_tries = 1 + max_retries

      # We attempt the operation on the agent multiple times until the agent
      # thinks that it succeeded. But we will only verify once the agent thinks
      # it succeeded. We do not give multiple chances to satisfy the
      # verification.
      for i in range(max_tries):
        attempt_info = execution_trace.new_attempt()
        status = None
        status = test_case.operation.execute(agent=self.testing_agent)
        status.wait(trace_every=full_trace)

        summary = status.error or ('Operation status OK' if status.finished_ok
                                   else 'Operation status Unknown')
        attempt_info.set_status(status, summary)

        if not status.exception_details:
          execution_trace.set_operation_summary('Completed test.')
          break
        if max_tries - i > 1:
          self.logger.warning(
              'Got an exception: %s.\nTrying again in %r secs...',
              status.exception_details, retry_interval_secs)
          time.sleep(retry_interval_secs)
        elif max_tries > 1:
          execution_trace.set_operation_summary('Gave up retrying operation.')
          self.logger.error('Giving up retrying test.')

      # We're always going to verify the contract, even if the request itself
      # failed. We set the verification on the attempt here, but do not assert
      # anything. We'll assert below outside this try/catch handler.
      verify_results = test_case.contract.verify()
      execution_trace.set_verify_results(verify_results)
      final_status_ok = self.verifyFinalStatusOk(
          status, timeout_ok=timeout_ok,
          final_attempt=attempt_info,
          execution_trace=execution_trace)
      context_relation = ('VALID' if (final_status_ok and verify_results)
                          else 'INVALID')
    except BaseException as ex:
      context_relation = 'ERROR'
      execution_trace.set_exception(ex)
      if attempt_info is None:
        execution_trace.set_exception(ex, traceback.format_exc())
      elif not attempt_info.completed:
        # Exception happened during the attempt as opposed to during our
        # verification afterwards.
        attempt_info.set_exception(ex, traceback.format_exc())

      try:
        self.logger.error('Test failed with exception: %s', ex)
        self.logger.error('Last status was:\n%s', str(status))
        self.logger.debug('Exception was at:\n%s', traceback.format_exc())
      except BaseException as unexpected:
        self.logger.error(
            'Unexpected error {0}\nHandling original exception {1}',
            unexpected, ex)
        self.logger.debug('Unexpected exception was at:\n%s',
                          traceback.format_exc())
      raise
    finally:
      self.log_end_test(test_case.title)
      self.report(execution_trace)
      JournalLogger.end_context(relation=context_relation)

    if not final_status_ok:
      self.raiseFinalStatusNotOk(status, attempt_info)

    if verify_results is not None:
      self.assertVerifyResults(verify_results)

