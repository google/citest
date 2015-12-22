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


"""Specialization of base.BaseTestCase for testing with citest.TestableAgents.

An AgentTestCase talks to both a TestableAgent and an external
observer, it then uses data from the external observer to verify expectations
made while talking to the TestableService.

The actual tests are written using operation_contract.OperationContract.
Each OperationContract contains an AgentOperation, which is sent to the
TestableAgent, and a Contract which specifies the expected system state
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
from ..base import scribe as base_scribe
from ..base import JsonSnapshotable
from .. import base
from .scenario_test_runner import ScenarioTestRunner


_DEFAULT_TEST_ID = time.strftime('%H%M%S')


class OperationContractExecutionAttempt(JsonSnapshotable):
  """Represents an individual attempt at running an OperationContract test case.

  This class captures the attempt and results so that it can be recorded in
  a snapshot.
  """

  @property
  def default_relation(self):
    """The default relation to assume when snapshotting.

    In practice this attempt is one of many in a list. The default_relation
    permits different elements to distinguish valid/invalid relationships.
    """
    if self.__verification is not None:
      return 'VALID' if self.__verification else 'INVALID'
    elif self.__exception is not None:
      return 'ERROR'
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

    if self.__status_summary:
      entity.add_metadata('summary', self.__status_summary)
    builder.make(entity, 'Name', self.__name)
    builder.make(entity, 'Duration', self.__stop - self.__start)

    if self.__status is not None:
      edge = builder.make(entity, 'OperationStatus', self.__status)
      if self.__status.finished:
        edge.add_metadata(
            'relation',
            builder.determine_valid_relation(self.__status.finished_ok))

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
    self.__attempts = []

  def set_verify_results(self, verify_results):
    """Sets the verification results once they are known."""
    self.__end = time.time()
    self.__verify_results = verify_results

  def set_exception(self, ex):
    """Sets the exception if one was encountered."""
    self.__end = time.time()
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
    if self.__verify_results is not None:
      entity.add_metadata(
          '_default_relation',
          builder.determine_valid_relation(self.__verify_results))
      builder.make(
          entity, 'Verification', self.__verify_results,
          relation=builder.determine_valid_relation(self.__verify_results))
    elif self.__exception is not None:
      entity.add_metadata('_default_relation', 'ERROR')

    if self.__attempts:
      edge = builder.make(entity, 'Attempts', list(reversed(self.__attempts)))
      final_relation = self.__attempts[-1].default_relation
      if final_relation is not None:
        edge.add_metadata('relation', final_relation)
        entity.add_metadata('_default_relation', final_relation)

    builder.make(entity, 'TestDuration', self.__end - self.__start)
    if self.__exception:
      builder.make_error(entity, 'Exception', self.__exception,
                         format='pre')

    if self.__operation_end is not None:
      builder.make(entity, 'OperationDuration',
                   self.__operation_end - self.__start)
      builder.make(entity, 'VerificationDuration',
                   self.__end - self.__operation_end)


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
    """The primary TestableAgent that is the focal point for the test."""
    return self._agent

  @property
  def bindings(self):
    """A dictionary used to bind configuration parameters for the test.

    Often these are somewhat arbitrary values that are used for multiple
    tests and might be desirable to control with command-line arguments
    when debugging or other develpment. The binding keys are all
    upper-case by convention for readability to make binding keys more
    distinct within the code.
    """
    return self._bindings

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

      agent: [TestableAgent] Primary agent used in this scenario.
          If not prodided then construct a new one with the class new_agent
          factory method.
    """
    self._bindings = bindings
    self._agent = agent or self.new_agent(bindings)
    self.__test_id = bindings.get('TEST_ID', _DEFAULT_TEST_ID)

  def substitute_variables(self, text):
    """Substitute $KEY with the bound value of KEY.

    Returns:
      Copy of text with bound variables substituted with their values.
    """
    return args_util.replace(text, self._bindings)

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


class AgentTestCase(base.BaseTestCase):
  """Base class for agent integration tests."""

  @property
  def report_scribe(self):
    """The Scribe used for producing the test report."""
    return ScenarioTestRunner.global_runner().report_scribe

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
  def testable_agent(self):
    """Return the primary TestableAgent for the current test scenario."""
    return self.scenario.agent

  def verifyContract(self, contract, report_section):
    """Verify the specified contract holds.

    Args:
      contract: [JsonContract] To verify.
      report_section: [ScribeRendererSection] To report verification into.

    Returns:
      ContractVerifyResults
    """
    # pylint: disable=invalid-name
    verify_results = contract.verify()

    clause_count = len(contract.clauses)
    plural = '' if clause_count == 1 else 's'
    if verify_results:
      summary = '{count} clause{plural} OK.'.format(
          count=clause_count, plural=plural)
    else:
      bad_count = len([elem for elem in verify_results.clause_results
                       if not elem.valid])
      summary = '{bad_count} of {clause_count} clause{plural} FAILED.'.format(
          bad_count=bad_count, clause_count=clause_count, plural=plural)

    relation = self.report_scribe.part_builder.determine_verified_relation(
        verify_results)
    scribe = base_scribe.Scribe(base_scribe.DETAIL_SCRIBE_REGISTRY)

    report_section.parts.append(
        self.report_scribe.part_builder.build_nested_part(
            name='Verification', value=verify_results,
            summary=summary, relation=relation))
    return verify_results

  def assertContract(self, contract, report_section):
    """Verify the specified contract holds, raise and exception if not."""
    # pylint: disable=invalid-name
    verify_results = self.verifyContract(contract, report_section)
    self.assertVerifyResults(verify_results)

  def assertVerifyResults(self, verify_results):
    """Assert that the results are valid.
    Args:
        verify_results: [ContractVerifyResults]
    Raises:
        AssertionError if not.
    """
    # pylint: disable=invalid-name
    scribe = base_scribe.Scribe(base_scribe.DETAIL_SCRIBE_REGISTRY)
    self.assertTrue(
        verify_results,
        'Contract clauses failed:\n{summary}\n{detail}'.format(
            summary=verify_results.enumerated_summary_message,
            detail=scribe.render_to_string(verify_results)))

  def assertFinalStatusOk(self, status, timeout_ok=False):
    """Verify that an agent request completed successfully.

    This is used to verify the messaging with the agent completed as expected
    before observing whether the expected side effects have taken place.

    Args:
      status: [AgentOperationStatus] The operation status.
      timeout_ok: [bool] If True then a timeout status is acceptable.
    """
    # pylint: disable=invalid-name
    # This is not because we dont want there to be an "exception".
    # Rather, we want the unit test to directly report what they were.
    if status.exception_details:
      self.logger.info(
          'status has exception_details=%s', status.exception_details)

    if not status.finished:
      if timeout_ok:
        self.logger.warning(
            'WARNING: request never completed [%s], but that is ok.',
            status.current_state)
        return

    if status.timed_out:
      self.logger.warning(
          'WARNING: It appears the status has timed out. Continuing anyway.')
      return

    scribe = base_scribe.Scribe(base_scribe.DETAIL_SCRIBE_REGISTRY)
    error = scribe.render_to_string(status)
    self.assertTrue(
        status.finished_ok, 'Did not finish_ok:\n{error}'.format(error=error))

  def make_test_case_report_section(self, test_case):
    """Creates a new section in the test report for the given test case.

    Args:
      test_case: [OperationContract] Specifies the test case.
    """
    return self.report_scribe.make_section(title=test_case.title)

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

    section = self.make_test_case_report_section(test_case)
    execution_trace = OperationContractExecutionTrace(test_case)
    verify_results = None

    try:
      max_tries = 1 + max_retries
      for i in range(max_tries):
        attempt_info = execution_trace.new_attempt()
        status = None
        status = test_case.operation.execute(agent=self.testable_agent)
        status.wait(trace_every=full_trace)

        summary = status.error or ('Operation status OK' if status.finished_ok
                                   else 'Operation status Unknown')
        attempt_info.set_status(status, summary)

        section.parts.append(
            self.report_scribe.part_builder.build_input_part(
                name='Attempt {count}'.format(count=i),
                value=status, summary=summary))

        if not status.exception_details:
          execution_trace.set_operation_summary('Completed test.')
          break
        if max_tries - i > 1:
          self.logger.warning(
              'Got an exception: %s.\nTrying again in %d secs...',
              status.exception_details, retry_interval_secs)
          time.sleep(retry_interval_secs)
        elif max_tries > 1:
          execution_trace.set_operation_summary('Gave up retrying operation.')
          self.logger.error('Giving up retrying test.')

      verify_results = self.verifyContract(test_case.contract, section)
      execution_trace.set_verify_results(verify_results)
    except BaseException as ex:
      error = base_scribe.Scribe().render_to_string(status)
      execution_trace.set_exception(ex)
      section.parts.append(self.report_scribe.build_part('EXCEPTION', ex))
      self.logger.error('Test failed with exception: %s', ex)

      self.logger.error('Last status was:\n%s', error)
      self.logger.debug('Exception was at:\n%s', traceback.format_exc())
      raise
    finally:
      self.log_end_test(test_case.title)
      self.report(section)
      self.report(execution_trace)

      self.assertFinalStatusOk(status, timeout_ok=timeout_ok)
      if verify_results is not None:
        self.assertVerifyResults(verify_results)
