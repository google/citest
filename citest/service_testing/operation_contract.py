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


"""Specifies test cases using BaseAgents."""

from ..base import JsonSnapshotable


class OperationContract(JsonSnapshotable):
  """Specifies a testable operation and contract to verify it.

  This is essentially a "test case" using  BaseAgents.
  """
  @property
  def title(self):
    """The name of the test case."""
    return self.__operation.title

  @property
  def operation(self):
    """The AgentOperation to perform."""
    return self.__operation

  @property
  def contract(self):
    """The json.Contract to verify the operation."""
    return self.__contract

  @property
  def status_collector(self):
    """The callable(OperationStatus) if any was bound.

    The StatusCollector can be used to observe the operation status
    and collect any information from it.
    """
    return self.__status_collector

  @property
  def cleanup(self):
    """The callable(OperationStatus, ContractVerifyResult) if any was bound.

    The cleanup can be used to perform any post-operation cleanup
    after the contract has been verified. It is called regardless of
    success or failure.
    """
    return self.__cleanup

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make(entity, 'Operation', self.__operation)
    snapshot.edge_builder.make(entity, 'Contract', self.__contract)

  def __init__(self, operation, contract,
               status_collector=None, cleanup=None):
    """Construct instance.

    Args:
      operation: [AgentOperation] To be performed.
      contract: [JsonContract] To verify operation.
      status_collector: [Callable(OperationStatus)] Takes OperationStatus.
      cleanup: [Callable(OperationStatus, ContractVerifyResult)]
          Perform any post-test cleanup.
    """
    self.__operation = operation
    self.__contract = contract
    self.__status_collector = status_collector
    self.__cleanup = cleanup
