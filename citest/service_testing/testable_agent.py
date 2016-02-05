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


"""Core adapter for the external system being tested to the citest framework.

Agents perform AgentOperations, which are messaging events between the citest
agent and the external system being tested. AgentOperation are asynchronous
and adapt the asynchronous state using AgentOperationStatus.

Specific implementation details about the operation results or messaging
information can be obtained from the AgentOperation.

Verification is performed independently using json.Contract.
"""


import logging
import time

from ..base import JsonScrubber
from ..base import JsonSnapshotable
from ..base import JournalLogger


class AgentError(Exception, JsonSnapshotable):
  """Denotes an error reported by a TestableAgent."""

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_error(entity, 'Message', self.message)

  def __init__(self, message):
    super(AgentError, self).__init__(message)

  def __str__(self):
    return self.message or self.__class__.__name__

  def __eq__(self, error):
    return (self.__class__ == error.__class__
            and self.message == error.message)


class TestableAgent(JsonSnapshotable):
  """Base class for adapting services and observers into the citest framework.

  The base class does not introduce any significant behavior, but the intent
  of TestableAgent is to provide an adapter for interacting with the services
  being tested, and (for convenience) the observers collecting observation
  data. The exact methods for doing this are introduced as the agents become
  specialized to the mechanism that will be needed and the particular APIs or
  protocols they use.

  Attributes:
  """
  @property
  def config_dict(self):
    """Property dictionary holding configuration information for the agent."""
    return self.__config_dict

  @property
  def default_max_wait_secs(self):
    """Number of seconds the agent should wait() on status by default.

    A value of -1 is indefinite.
    """
    return self.__default_max_wait_secs

  @default_max_wait_secs.setter
  def default_max_wait_secs(self, secs):
    """Sets the default wait() timeout period."""
    self.__default_max_wait_secs = secs

  def __init__(self):
    self.logger = logging.getLogger(__name__)
    self.nojournal_logger = logging.LoggerAdapter(
        self.logger, {'citest_journal': {'nojournal':True}})
    self.__default_max_wait_secs = -1
    self.__config_dict = {}

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder

    # Make sure there arent passwords in here.
    scrubbed_config = JsonScrubber()(self.__config_dict)
    builder.make_control(entity, 'Max Wait Secs', self.__default_max_wait_secs)
    builder.make_control(entity, 'Configuration', scrubbed_config)


class AgentOperationStatus(JsonSnapshotable):
  """Base class for current Status on AgentOperation.

  The operations performed by testable agents have disparate results depending
  on the underlying service in question. Besides the data types being
  different, the protocols are as well. Often services are asynchronous,
  returning a handle used to query for current status information. This
  class makes an attempt at providing an abstract way to manage the protocol
  to obtain the status of an operation, and also to get the raw result details.

  The interpretation of these details is not abstracted, thus requires
  awareness of the underlying agent and its semantics to interpret. However,
  the status can be used for generic flow control and reporting.

  Properties requiring specialization:
    finished:
    finished_ok:
    timed_out:
    id:
    detail:
  """
  @property
  def finished(self):
    """Indicates whether future refresh() will change the status."""
    raise NotImplementedError(
        'finished was not specialized on {0}.'.format(self.__class__))

  @property
  def finished_ok(self):
    """Indicates that the status finished successfully."""
    raise NotImplementedError(
        'finished_ok was not specialized on {0}.'.format(self.__class__))

  @property
  def timed_out(self):
    """Indicates the underlying operation finished by timing out."""
    raise NotImplementedError(
        'timed_out was not specialized on {0}.'.format(self.__class__))

  @property
  def detail(self):
    """Contains the detailed results from the agent."""
    raise NotImplementedError(
        'detail was not specialized on {0}.'.format(self.__class__))

  @property
  def id(self):
    """Contains an internal identifier for logging purposes."""
    raise NotImplementedError(
        'id was not specialized on {0}.'.format(self.__class__))

  @property
  def error(self):
    """Contains the error object, if any."""
    return None

  @property
  def exception_details(self):
    """Contains a guess of the cause of the error."""
    return None

  @property
  def operation(self):
    """A reference to the AgentOperation this status is for."""
    return self.__operation

  @property
  def agent(self):
    """A reference to the TestableAgent that executed the |operation|."""
    return self.__operation.agent

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    builder.make(entity, 'ID', self.id)
    builder.make_output(entity, 'Finished', self.finished)
    if self.finished:
      builder.make(entity, 'Finished OK', self.finished_ok,
                   relation='VALID' if self.finished_ok else 'INVALID')
    else:
      builder.make(entity, 'Timed Out', self.timed_out)
    if self.error:
      builder.make_error(entity, 'Error', self.error)
    if self.detail:
      builder.make_data(entity, 'Detail', self.detail, format='json')
    if self.exception_details:
      builder.make_error(entity, 'Exception Details', self.exception_details,
                         format='json')
    builder.make_input(entity, 'Operation', self.operation)
    builder.make_mechanism(
        entity, 'Agent Class', self.agent.__class__.__name__)

  def __init__(self, operation):
    """Constructs status instance.

    Args:
      operation: [AgentOperation] The status is for.
    """
    self.__operation = operation

  def refresh(self, trace=True):
    """Refresh the status with the current data.

    Args:
      trace: [bool] Whether or not to trace the call through the agent update.
    """
    # pylint: disable=unused-argument
    if self.finished:
      return

    raise NotImplementedError(
        self.__class__.__name__ + '.refresh() needs to be specialized.')

  def wait(self, poll_every_secs=1, max_secs=-1,
           trace_every=False, trace_first=True):
    """Wait until the status reaches a final state.

    Args:
      poll_every_secs: [int] Interval to refresh() from the proxy.
      max_secs: [int] Most seconds to wait before giving up.
          0 is a poll, -1 is unbounded, otherwise number of seconds.
      trace_every: [bool] Whether or not to log every poll request.
      trace_first: [bool] Whether to log the first poll request.
    """
    if self.finished:
      return

    if max_secs < 0:
      max_secs = self.operation.max_wait_secs

    message = 'Wait on id={0}, max_secs={1}'.format(self.id, max_secs)
    JournalLogger.begin_context(message)
    context_relation = 'ERROR'
    try:
      self.refresh(trace=trace_first)
      ok = self.__wait_helper(poll_every_secs, max_secs, trace_every)
      context_relation = 'VALID' if ok else 'INVALID'
    finally:
      JournalLogger.end_context(relation=context_relation)

  def __wait_helper(self, poll_every_secs, max_secs, trace):
    logger = logging.getLogger(__name__)
    secs_remaining = max_secs
    log_secs_remaining = 0
    while not self.finished:
        # pylint: disable=bad-indentation
        if secs_remaining <= 0 and max_secs > 0:
          logger.debug('Timed out')
          return False

        sleep_secs = (poll_every_secs if max_secs < 0
                      else min(secs_remaining, poll_every_secs))

        # Write something into the log file to indicate we are still here.
        if log_secs_remaining < sleep_secs:
          logger.debug(
              'Still waiting (polling again in %d) with %d secs remaining',
              sleep_secs, secs_remaining)
          # Hardcoded once-a-minute confirmation that we're still waiting.
          log_secs_remaining = 60
        else:
          log_secs_remaining -= sleep_secs

        self._do_sleep(sleep_secs)
        secs_remaining -= sleep_secs
        self.refresh(trace=trace)

    return True

  def _do_sleep(self, secs):
    """Hook so we can mock out sleep calls in wait()'s polling loop.

    Args:
      secs: [int] Number of seconds to sleep
    """
    time.sleep(secs)


class AgentOperation(JsonSnapshotable):
  """Base class abstraction for a testable operation executed through an agent.

  AgentOperation is a first-class operation that can be executed at some point
  in the future. The intention is the operation species the activity that
  is to be tested for a given test case.

  Specialized agents will specialize operations as needed to interact with
  the underlying system. Operations are not intended to be used by observers
  to collect state information. Only to capture the test activities.
  """
  @property
  def agent(self):
    """The TestableAgent to execute the operation.

    This may be None if the binding is deferred. However, it must be bound
    before it is executed.
    """
    return self.__agent

  @property
  def title(self):
    """The name of the operation for tracing/reporting purposes."""
    return self.__title

  @property
  def max_wait_secs(self):
    """How long an OperationStatus for this operation can wait."""
    if self.__max_wait_secs:
      return self.__max_wait_secs
    if self.__agent:
      return self.__agent.default_max_wait_secs
    return 0

  def bind_agent(self, agent):
    """Binds the agent to the operation.

    Args:
      agent: [TestableAgent] If None then unbind.
    """
    if self.__agent:
      logging.getLogger(__name__).warning('Rebinding agent on ' + str(self))
    self.__agent = agent

  def __init__(self, title, agent=None):
    """Construct operation instance.

    Args:
      title: [string] The name of the operation for reporting purposes only.
      agent: [TestableAgent] The agent performing the operation can be bound
          later, but must eventually be bound.
    """
    self.__title = title
    self.__agent = agent
    self.__max_wait_secs = None

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    builder.make(entity, 'Title', self.title)
    builder.make_mechanism(
        entity, 'Agent Class', self.agent.__class__.__name__)
    builder.make_control(entity, 'Max Wait Secs', self.max_wait_secs)

  def execute(self):
    """Have the bound agent perform this operation.

    This method must be specialized.

    Returns:
      OperationStatus for this invocation.
    """
    raise NotImplementedError(
        'execute was not specialized on {0}.'.format(self.__class__))
