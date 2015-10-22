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


# An AgentTestCase talks to both a TestableAgent and an external
# observer, it then uses data from the external observer to verify expectations
# made while talking to the TestableService.
#
# The actual tests are written using operation_contract.OperationContract.
# Each OperationContract contains an AgentOperation, which is sent to the
# TestableAgent, and a Contract which specifies the expected system state
# (resources it expects to find and/or resources it does not expect to find).
#
# A detailed log file is written as the test runs for more information.
# The default log file name is the name of the python module,
# but can be changed with --log_filename and --log_dir.

# Standard python modules.
import argparse
from multiprocessing.pool import ThreadPool
import time
import traceback

# Our modules.
from ..base import args_util
from ..base import scribe as base_scribe
from .. import base
from .. import json_contract as jc
from scenario_test_runner import ScenarioTestRunner


_DEFAULT_TEST_ID = time.strftime('%H%M%S')


class AgentTestScenario(object):
  """Class for sharing scenario data and state across different test cases.

  This class does not really define much behavior. It just manages
  a set of parameters. The intent is for specialized classes to
  define the OperationTestCases, using the parameters to determine
  the final values to use.

  Attributes:
    agent: The TestableAgent that is being used for the test.
        Presumably there is only one, and it is bound at construction time.

    bindings: A dictionary of name/value pairs used to bind configuration
        parameters for the test. Often these are somewhat arbitrary values
        that are used for multiple tests and might be desirable to control
        with command-line arguments when debugging or other develpment.
        The binding keys are all upper-case by convention for readability
        to make binding keys more distinct within the code.
  """

  DEFAULT_TEST_ID = _DEFAULT_TEST_ID

  @property
  def agent(self):
    return self._agent

  @property
  def bindings(self):
    return self._bindings

  @staticmethod
  def make_scenario(scenarioClass, bindings):
    return scenarioClass(bindings)

  @property
  def test_id(self):
    return self.__test_id

  def __init__(self, bindings, agent=None):
    """Construct scenario

    Args:
      bindings: Dictionary of key/value configuration values.
        The keys are in upper case. The actual keys are not standardized,
        rather the scenarios may have a set of parameters that they use
        for their needs.

      agent: The TestableAgent to use for this scenario.
             If not prodided then construct a new one with the class new_agent
             factory method.
    """
    self._bindings = bindings
    self._agent = agent or self.new_agent(bindings)
    self.__test_id = bindings.get('TEST_ID', _DEFAULT_TEST_ID)

  def substitute_variables(self, s):
    """Substitute $KEY with the bound value of KEY.

    Returns:
      Copy of s with bound variables substituted with their values.
    """
    return args_util.replace(s, self._bindings)

  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    """Adds arguments introduced by the BaseTestCase module.

    Args:
      parser: argparse.ArgumentParser instance to add to.
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
    return ScenarioTestRunner.global_runner().report_scribe

  def report(self, obj):
    ScenarioTestRunner.global_runner().report(obj)

  @property
  def scenario(self):
    return ScenarioTestRunner.global_runner().scenario

  @property
  def testable_agent(self):
    return self.scenario.agent

  def assertContract(self, contract, report_section):
    """Verify the specified contract holds.

    Args:
      contract: The JsonContract to verify.
      report_section: The scribe_section to report verification into.
    """
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

    self.assertTrue(
        verify_results,
        'Contract clauses failed:\n{summary}\n{detail}'.format(
            summary=verify_results.enumerated_summary_message,
            detail=scribe.render_to_string(verify_results)))

  def confirmFinalStatusOk(self, status, timeout_ok=False):
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
    return self.report_scribe.make_section(title=test_case.title)

  def run_test_case_list(
      self, test_case_list, max_concurrent, timeout_ok=False,
      max_retries=0, retry_interval_secs=5, full_trace=False):
    num_threads = min(max_concurrent, len(test_case_list))
    pool = ThreadPool(processes=num_threads)
    def run_one(test_case):
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
      test_case: An OperationContract.
      timeout_ok: Whether a testable_agent.AgentOperationStatus timeout implies
          a test failure. If it is ok to timeout, then we'll still verify the
          contracts, but skip the final status check if there is no final
          status yet.
      max_retries: If > 0, then rerun the test until it succeeds this number
          of times. A value of 0 indicates the test is run only once.
      retry_interval_secs: The number of seconds to wait between retries.
      full_trace: If true, then apply as much tracing as possible, otherwise
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
    try:
      max_tries = 1 + max_retries
      for i in range(max_tries):
        status = None
        status = test_case.operation.execute(agent=self.testable_agent)
        status.wait(trace_every=full_trace)

        summary = status.error or ('Operation status OK' if status.finished_ok
                                   else 'Operation status Unknown')
        section.parts.append(self.report_scribe.part_builder.build_input_part(
                             name='Attempt {count}'.format(count=i),
                             value=status, summary=summary))

        if not status.exception_details:
          break
        if max_tries - i > 1:
          self.logger.warning(
              'Got an exception: %s.\nTrying again in %d secs...',
              status.exception_details, retry_interval_secs)
          time.sleep(retry_interval_secs)
        elif max_tries > 1:
          self.logger.error('Giving up retries.')

      self.confirmFinalStatusOk(status, timeout_ok=timeout_ok)
      self.assertContract(test_case.contract, section)
    except Exception as e:
      error = base_scribe.Scribe().render_to_string(status)
      self.logger.error('Test failed with exception: %s', e)
      self.logger.error('Last status was:\n%s', error)
      self.logger.debug('Exception was at:\n%s', traceback.format_exc())
      section.parts.append(self.report_scribe.build_part('EXCEPTION', e))
      raise
    finally:
      self.log_end_test(test_case.title)
      self.report(section)
