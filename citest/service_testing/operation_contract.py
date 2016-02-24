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

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make(entity, 'Operation', self.__operation)
    snapshot.edge_builder.make(entity, 'Contract', self.__contract)

  def __init__(self, operation, contract):
    """Construct instance.

    Args:
      operation: [AgentOperation] To be performed.
      contract: [JsonContract] To verify operation.
    """
    self.__operation = operation
    self.__contract = contract
