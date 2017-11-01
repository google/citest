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

"""A no-op operation does nothing. It is intended for observing invariants."""

from citest.service_testing import base_agent


class ConstantOperationStatus(base_agent.AgentOperationStatus):
  """An operation status meant for a NoOp operation.

  By default this is simply success. It could be configured to be an error.
  """

  @property
  def finished(self):
    """Implments AgentOperationStatus interface."""
    return True

  @property
  def finished_ok(self):
    """Implments AgentOperationStatus interface."""
    return self.__error is None

  @property
  def timed_out(self):
    """Implments AgentOperationStatus interface."""
    return False

  @property
  def detail(self):
    """Implments AgentOperationStatus interface."""
    return self.__detail

  @property
  def id(self):
    """Implments AgentOperationStatus interface."""
    return self.__id


  def __init__(self, operation, id='no-op', detail=None, error=None):
    """Constructor."""
    # pylint: disable=redefined-builtin
    super(ConstantOperationStatus, self).__init__(operation)
    self.__id = id
    self.__detail = detail
    self.__error = error


class NoOpOperation(base_agent.AgentOperation):
  """Implements an operation that succeeds without doing anything.

  This is intended to test invariants as a contract. The invariant is
  associated with this operation, thus can be tested using the same techniques
  as other interactions with the server that produce side effects.
  """

  def execute(self, agent=None):
    """Implments AgentOperation interface.

    Args:
      agent: [ignored] Complies with the AgentOperation interface.
    """
    # pylint: disable=unused-argument
    return ConstantOperationStatus(self)
