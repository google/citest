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


import logging
import time

from ..base.scribe import Scribable


class AgentError(Exception, Scribable):
  """Denotes an error reported by a TestableAgent."""
  def _make_scribe_parts(self, scribe):
    return [scribe.build_part('Message', self._message)]

  def __init__(self, message):
    self._message = message

  def __str__(self):
    return self._message or self.__class__.__name__

  def __eq__(self, error):
    return (self.__class__ == error.__class__
            and self._message == error._message)


class TestableAgent(object):
  """Base class for adapting services and observers into the citest framework.

  The base class does not introduce any significant behavior, but the intent
  of TestableAgent is to provide an adapter for interacting with the services
  being tested, and (for convenience) the observers collecting observation
  data. The exact methods for doing this are introduced as the agents become
  specialized to the mechanism that will be needed and the particular APIs or
  protocols they use.

  Attributes:
    config_dict: Generic property dictionary intended to capture configuration
        information for the agent.
    default_max_wait_secs: Acts as the default timeout when the agent waits
        on status. The base class defaults to -1, which is indefinite.
    default_max_wait_secs: Number of seconds operation status should wait
        when their wait() method is called without specifying a limit.
  """
  @property
  def config_dict(self):
    return self._config_dict

  @property
  def default_max_wait_secs(self):
    return self._default_max_wait_secs

  @default_max_wait_secs.setter
  def set_default_max_wait_secs(self, max):
    self._default_max_wait_secs = max

  def __init__(self):
    self.logger = logging.getLogger(__name__)
    self._default_max_wait_secs = -1
    self._config_dict = {}


class AgentOperationStatus(Scribable):
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

  Attributes requiring specialization:
    finished: Indicates whether future refresh() will change the status.
    finished_ok: Indicates that the status finished successfully.
    timed_out: Indicates the underlying operation finished by timing out.
    id: Contains an internal identifier for logging purposes.
    detail: Contains the detailed results from the agent.

  Attributes managed by base class:
    error: Contains the error, if any.
    exception_details: Contains a guess of the cause of the error.
    operation: A reference to the AgentOperation this status is for.
    agent: A reference to the Agent that executed the |operation|.
  """
  @property
  def finished(self):
    raise NotImplementedError(
        'finished was not specialized on {0}.'.format(self.__class__))

  @property
  def finished_ok(self):
    raise NotImplementedError(
        'finished_ok was not specialized on {0}.'.format(self.__class__))

  @property
  def timed_out(self):
    raise NotImplementedError(
        'timed_out was not specialized on {0}.'.format(self.__class__))

  @property
  def detail(self):
    raise NotImplementedError(
        'detail was not specialized on {0}.'.format(self.__class__))

  @property
  def id(self):
    raise NotImplementedError(
        'id was not specialized on {0}.'.format(self.__class__))

  @property
  def error(self):
    return self._error

  @property
  def exception_details(self):
    return None

  @property
  def operation(self):
    return self._operation

  @property
  def agent(self):
    return self._operation.agent

  def _make_scribe_parts(self, scribe):
    parts = []
    parts.extend([scribe.build_part('ID', self.id),
                  scribe.build_part('Finished', self.finished,
                                    relation=scribe.part_builder.OUTPUT)])
    if self.finished:
      relation = scribe.part_builder.determine_verified_relation(
          self.finished_ok)
      parts.append(
         scribe.build_part('Finished OK', self.finished_ok, relation=relation))
    else:
      parts.append(scribe.build_part('Timed Out', self.timed_out))
    if self.error:
      parts.append(scribe.build_json_part('Error', self.error,
                                          relation=scribe.part_builder.ERROR))
    if self.detail:
      parts.append(scribe.build_json_part('Detail', self.detail,
                                          relation=scribe.part_builder.OUTPUT))
    if self.exception_details:
      parts.append(
        scribe.build_json_part('Exception Details', self.exception_details,
                               relation=scribe.part_builder.ERROR))
    parts.extend(
        [scribe.part_builder.build_input_part('Operation', self.operation),
         scribe.build_part('Agent Class', self.agent.__class__.__name__,
                           relation=scribe.part_builder.MECHANISM)])
    return parts

  def __init__(self, operation):
    """Constructs status instance.

    Args:
      operation: AgentOperation this status is for.
    """
    self._error = None
    self._operation = operation

  def refresh(self, trace=True):
    """Refresh the status with the current data.

    Args:
      trace: Whether or not to trace the call through the agent update.
    """
    if self.finished:
      return

    raise NotImplementedError(
      self.__class__.__name__ + '.refresh() needs to be specialized.')

  def wait(self, poll_every_secs=1, max_secs=-1,
           trace_every=False, trace_first=True):
    """Wait until the status reaches a final state.

    Args:
      poll_every_secs: Interval to refresh() from the proxy.
      max_secs: Most seconds to wait before giving up.
          0 is a poll, -1 is unbounded, otherwise number of seconds.
      trace_every: Whether or not to log every poll request.
      trace_first: Whether to log the first poll request.
    """
    if self.finished:
      return

    if max_secs < 0:
      max_secs = self.operation.max_wait_secs

    logger = self.agent.logger
    trace = trace_first
    logger.debug('Wait on id=%s, max_secs=%d', self.id, max_secs)
    self.refresh(trace=trace)
    trace = trace_every

    secs_remaining = max_secs
    while not self.finished:
        if secs_remaining <= 0 and max_secs > 0:
          logger.debug('Timed out')
          return

        sleep_secs = (poll_every_secs if max_secs < 0
                      else min(secs_remaining, poll_every_secs))
        self._sleep(sleep_secs)
        secs_remaining -= sleep_secs
        self.refresh(trace=trace)

  def _sleep(self, secs):
    """Hook so we can mock out sleep calls in wait()'s polling loop.

    Args:
      secs: Number of seconds to sleep
    """
    time.sleep(secs)


class AgentOperation(Scribable):
  """Base class abstraction for a testable operation executed through an agent.

  AgentOperation is a first-class operation that can be executed at some point
  in the future. The intention is the operation species the activity that
  is to be tested for a given test case.

  Specialized agents will specialize operations as needed to interact with
  the underlying system. Operations are not intended to be used by observers
  to collect state information. Only to capture the test activities.

  Attributes:
    agent: The agent to execute the operation may be None if the binding
        is deferred, but must be bound before it is executed.
    title: The name of the operation for tracing/reporting purposes.
    max_wait_secs: How long an OperationStatus for this operation can wait.
  """
  @property
  def agent(self):
    return self._agent

  @property
  def title(self):
    return self._title

  @property
  def max_wait_secs(self):
    if self._max_wait_secs:
      return self._max_wait_secs
    if self._agent:
      return self._agent.default_max_wait_secs
    return 0

  def bind_agent(self, agent):
    if self._agent:
      logging.getLogger(__name__).warning('Rebinding agent on ' + str(self))
    self._agent = agent

  def __init__(self, title, agent=None):
    """Construct operation instance.

    Args:
      title: The name of the operation for reporting purposes only.
      agent: The agent performing the operation can be bound later,
           but must eventually be bound.
    """
    self._title = title
    self._agent = agent
    self._max_wait_secs = None

  def _make_scribe_parts(self, scribe):
    return [scribe.build_part('Title', self.title),
            scribe.build_part('Agent Class', self.agent.__class__.__name__,
                              relation=scribe.part_builder.MECHANISM),
            scribe.build_part('Max Wait Secs', self.max_wait_secs,
                              relation=scribe.part_builder.CONTROL)]

  def execute(self):
    """Have the bound agent perform this operation.

    This method must be specialized.

    Returns:
      OperationStatus for this invocation.
    """
    raise NotImplementedError(
        'execute was not specialized on {0}.'.format(self.__class__))
