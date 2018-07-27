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
import re
import subprocess

from citest.base import JournalLogger
from citest.base import JsonSnapshotableEntity
import citest.json_contract as jc
import citest.json_predicate as jp
from . import base_agent


class CliResponseType(collections.namedtuple('CliResponseType',
                                             ['exit_code', 'output', 'error']),
                      JsonSnapshotableEntity):
  """Holds the results from running the command-line program.

  Attributes:
    exit_code: The program exit code.
    output: The program stdout.
    error: The program stderr (or other error explaining failure to run).
  """
  def ok(self):
    """Returns True if the call succeeded, False otherwise."""
    return self.exit_code == 0

  def __str__(self):
    return 'exit_code={0} output={1!r} error={2!r}'.format(
        self.exit_code, self.output, self.error)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    builder.make(entity, 'Exit Code', self.exit_code)
    if self.error:
      builder.make_error(entity, 'stderr', self.error, format='json')
    if self.output:
      builder.make_output(entity, 'stdout', self.output, format='json')


class CliRunStatus(base_agent.AgentOperationStatus):
  """Concrete specialization of AgentOperationStatus for CliAgent operations.

  Attributes:
    See base_agent.AgentOperationStatus.
  """
  @property
  def finished(self):
    return True

  @property
  def finished_ok(self):
    return self.__cli_response.ok()

  @property
  def timed_out(self):
    return False

  @property
  def detail(self):
    return self.__cli_response.output

  @property
  def error(self):
    return self.__cli_response.error

  def __init__(self, operation, cli_response):
    super(CliRunStatus, self).__init__(operation)
    self.__cli_response = cli_response

  def __cmp__(self, response):
    return self.__cli_response.__cmp__(response.__cli_response)

  def __str__(self):
    return 'cli_response={0}'.format(self.__cli_response)

  def update_cli_response(self, cli_response):
    self.__cli_response = cli_response


class CliAgentRunError(base_agent.AgentError):
  """An error for reporting execution failures.

  Properties:
    run_response: The original CliResponseType reporting the error.
  """
  @property
  def run_response(self):
    return self.__run_response

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    super(CliAgentRunError, self).export_to_json_snapshot(snapshot, entity)
    snapshot.edge_builder.make_data(
        entity, 'Cli Response', self.__run_response)

  def __init__(self, agent, run_response):
    super(CliAgentRunError, self).__init__(run_response.error)
    self.__run_response = run_response

  def __eq__(self, error):
    return self.__run_response == error.__run_response

  def match_regex(self, regex):
    """Attempt to match a regular expression against the error.

    Args:
      regex: The regular expression to match against

    Returns:
      re.MatchObject or None
    """
    return re.search(regex, self.__run_response.error, re.MULTILINE)


class CliAgent(base_agent.BaseAgent):
  """A specialization of BaseAgent for invoking command-line programs."""

  def __init__(self, program, output_scrubber=None, logger=None):
    """Standard constructor.

    Args:
      program: A path of the program to execute.
      logger: The logger if other than the default.
    """
    super(CliAgent, self).__init__(logger=logger)
    self.__program = program
    self.__output_scrubber = output_scrubber

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Program', self.__program)
    super(CliAgent, self).export_to_json_snapshot(snapshot, entity)

  def _new_run_operation(self, title, args, max_wait_secs=None):
    return CliRunOperation(title, args, self, max_wait_secs=max_wait_secs)

  def _new_status(self, operation, cli_response):
    return CliRunStatus(operation, cli_response)

  def _args_to_full_commandline(self, args):
    """Returns the complete commandline given a desired argument list.

    This is an internal method used to ensure that the arguments are ultimately
    consistent if needed, regardless of how the agent is invoked.
    """
    return [self.__program] + args

  def run(self, args, output_scrubber=None):
    """Run the specified command.

    Args:
      args: The list of command-line arguments for self.__program.

    Returns:
      CliResponseType tuple containing program execution results.
    """
    command = self._args_to_full_commandline(args)
    log_msg = 'spawn {0} "{1}"'.format(command[0], '" "'.join(command[1:]))
    JournalLogger.journal_or_log(log_msg,
                                 _logger=self.logger,
                                 _context='request')

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True)
    stdout, stderr = process.communicate()
    if stdout is not None:
      stdout = bytes.decode(stdout)
    if stderr is not None:
      stderr = bytes.decode(stderr)
    scrubber = output_scrubber or self.__output_scrubber
    if scrubber:
      log_msg = 'Scrubbing output with {0}'.format(scrubber.__class__.__name__)
      JournalLogger.journal_or_log(log_msg, _logger=self.logger)
      stdout = scrubber(stdout)

    # Strip leading/trailing eolns that program may add to errors and output.
    stderr = stderr.strip()
    stdout = stdout.strip()
    code = process.returncode

    # Always log to journal
    if stdout and stderr:
      which = 'both stdout and stderr'
      output_json = {'stdout':stdout, 'stderr':stderr}
    else:
      which = 'stderr' if stderr else 'stdout'
      output_json = stderr if stderr else stdout
    if output_json:
      JournalLogger.journal_or_log_detail(
          'Result Code {0} / {1}'.format(code, which), output_json,
          _logger=self.logger, _context='response')
    else:
      JournalLogger.journal_or_log(
          'Result Code {0} / no ouptut'.format(code),
          _logger=self.logger,
          _context='response')

    return CliResponseType(code, stdout, stderr)


class CliRunOperation(base_agent.AgentOperation):
  """Specialization of AgentOperation that invokes a program."""
  def __init__(self, title, args, cli_agent=None, max_wait_secs=None):
    super(CliRunOperation, self).__init__(title, cli_agent,
                                          max_wait_secs=max_wait_secs)
    if cli_agent and not isinstance(cli_agent, CliAgent):
      raise TypeError(
          'cli_agent is not CliAgent: {0}'.format(cli_agent.__class__))
    self.__args = list(args)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Args', self.__args)
    super(CliRunOperation, self).export_to_json_snapshot(snapshot, entity)

  def execute(self, agent=None):
    if not agent:
      agent = self.agent
    elif not isinstance(agent, CliAgent):
      raise TypeError(
          'agent is not CliAgent: {0}'.format(agent.__class__))

    cli_response = agent.run(self.__args)
    status = agent._new_status(self, cli_response)
    agent.nojournal_logger.debug('Returning status %s', status)
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
    self.__error_regex = error_regex

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Regex', self.__error_regex)
    super(CliAgentObservationFailureVerifier, self).export_to_json_snapshot(
        snapshot, entity)

  def _error_comment_or_none(self, error):
    if (isinstance(error, CliAgentRunError)
        and error.match_regex(self.__error_regex)):
      return 'Error matches {0}'.format(self.__error_regex)


class CliAgentRunErrorPredicate(jp.ValuePredicate):
  """An Predicate expects specify CliAgentRunError."""

  def __init__(self, title, error_regex):
    """Constructs the clause with the acceptable error regex.

    Args:
      title: Verifier name for reporting purposes only.
      error_regex: Regex pattern for errors we're looking for.
    """
    super(CliAgentRunErrorPredicate, self).__init__()
    self.__title = title
    self.__error_regex = error_regex

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    entity.add_metadata('_title', self.__title)
    snapshot.edge_builder.make(entity, 'Title', self.__title)
    snapshot.edge_builder.make_control(entity, 'Regex', self.__error_regex)

  def __call__(self, context, value):
    """Implements ValuePredicate interface."""
    if not isinstance(value, CliAgentRunError):
      return jp.JsonError('Expected program to fail, but it did not')

    ok = value.match_regex(self.__error_regex)
    return jp.PredicateResult(ok is not None)

