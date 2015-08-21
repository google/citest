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


import collections
import logging
import re
import subprocess

from ..base.scribe import Scribable
from .. import json_contract as jc
from . import testable_agent

class CliResponseType(collections.namedtuple('CliResponseType',
                                             ['retcode', 'output', 'error']),
                      Scribable):
  """Holds the results from running the command-line program.

  Attributes:
    retcode: The program exit code.
    output: The program stdout.
    error: The program stderr (or other error explaining failure to run).
  """
  def __str__(self):
    return 'retcode={0} output={1!r} error={2!r}'.format(
      self.retcode, self.output, self.error)

  def _make_scribe_parts(self, scribe):
    label = 'Response Error' if self.error else 'Response Data'
    data = self.error if self.error else self.output
    parts = [scribe.build_part('Exit Code', self.retcode)]
    if self.error:
      parts.append(scribe.build_json_part('stderr', self.error))
    if self.output:
      parts.append(scribe.build_json_part('stdout', self.output))
    return parts


class CliRunStatus(testable_agent.AgentOperationStatus):
  """Concrete specialization of AgentOperationStatus for CliAgent operations.

  Attributes:
    See testable_agent.AgentOperationStatus.
  """
  @property
  def finished(self):
    return True

  @property
  def finished_ok(self):
    return self._cli_response.retcode == 0

  @property
  def timed_out(self):
    return False

  @property
  def detail(self):
    return self._cli_response.output

  @property
  def error(self):
    return self._cli_response.error

  def __init__(self, operation, cli_response):
    super(CliRunStatus, self).__init__(operation)
    self._cli_response = cli_response

  def __cmp__(self, response):
    return self._cli_response.__cmp__(response._cli_response)

  def __str__(self):
    return 'cli_response={0}'.format(self._cli_response)

  def update_cli_response(self, cli_response):
    self._cli_response = cli_response


class CliAgentRunError(testable_agent.AgentError):
  """An error for reporting execution failures.

  Properties:
    run_response: The original CliResponseType reporting the error.
  """
  @property
  def run_response(self):
    return self._run_response

  def _make_scribe_parts(self, scribe):
    return (super(CliAgentRunError, self)._make_scribe_parts(scribe)
            + [scribe.build_nested_part('Cli Response', self._run_response)])

  def __init__(self, agent, run_response):
    super(CliAgentRunError, self).__init__(run_response.error)
    self._run_response = run_response

  def __eq__(self, error):
    return self._run_response == error._run_response

  def match_regex(self, regex):
    """Attempt to match a regular expression against the error.

    Args:
      regex: The regular expression to match against

    Returns:
      re.MatchObject or None
    """
    return re.search(regex, self._run_response.error, re.MULTILINE)


class CliAgent(testable_agent.TestableAgent):
  """A specialization of TestableAgent for invoking command-line programs."""

  def __init__(self, program):
    """Standard constructor.

    Args:
      program: A path of the program to execute.
    """
    super(CliAgent, self).__init__()
    self._program = program
    self._strip_trailing_eoln = True

  def _make_scribe_parts(self, scribe):
    return ([scribe.build_part('Program', self._program)]
            + super(CliAgent, self)._make_scribe_parts(scribe))

  def _new_run_operation(self, title, args):
    return CliRunOperation(title, args, self)

  def _new_status(self, operation, cli_response):
    return CliRunStatus(operation, cli_response)

  def run(self, args, trace=True):
    """Run the specified command.

    Args:
      args: The list of command-line arguments for self._program.
      trace: If True then we should trace the call/response.

    Returns:
      CliResponseType tuple containing program execution results.
    """
    cmd = [self._program] + args
    if trace:
      logger = logging.getLogger(__name__)
      logger.debug(cmd)
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    code = process.returncode

    # Strip off leading/trailing eolns that program may add to errors and output.
    error = error.strip()
    output = output.strip()
    if trace:
      logger.debug('-> %d: err=[%s] %s', code, error, output)
    return CliResponseType(code, output, error)


class CliRunOperation(testable_agent.AgentOperation):
  """Specialization of AgentOperation that invokes a program."""
  def __init__(self, title, args, cli_agent=None):
    super(CliRunOperation, self).__init__(title, cli_agent)
    if cli_agent and not isinstance(cli_agent, CliAgent):
      raise TypeError(
          'cli_agent is not CliAgent: {0}'.format(cli_agent.__class__))
    self._args = list(args)

  def _make_scribe_parts(self, scribe):
    return ([scribe.build_part('Args', self._args)]
            + super(CliRunOperation, self)._make_scribe_parts(scribe))

  def execute(self, agent=None, trace=True):
    if not agent:
      agent = self.agent
    elif not isinstance(agent, CliAgent):
      raise TypeError(
          'agent is not CliAgent: {0}'.format(agent.__class__))

    cli_response = agent.run(self._args, trace=trace)
    status = agent._new_status(self, cli_response)
    if trace:
      agent.logger.debug('Returning status %s', status)
    return status


class CliAgentObservationFailureVerifier(jc.ObservationFailureVerifier):
  """An ObservationVerifier that expects specific errors from stderr."""

  def __init__(self, title, error_regex):
    """Constructs the clause with the acceptable error regex.

    Args:
      title: Verifier name for reporting purposes only.
      error_regex: Regex pattern for errors we're looking for.
    """
    super(CliAgentObservationFailureVerifier, self).__init__(title)
    self._error_regex = error_regex

  def _make_scribe_parts(self, scribe):
    parts = [scribe.build_part(
        'Regex', self._error_regex, relation=scribe.part_builder.CONTROL)]
    inherited = super(
        CliAgentObservationFailureVerifier, self)._make_scribe_parts(scribe)
    return parts + inherited

  def _error_comment_or_none(self, error):
    if (isinstance(error, CliAgentRunError)
        and error.match_regex(self._error_regex)):
      return 'Error matches {0}'.format(self._error_regex)
