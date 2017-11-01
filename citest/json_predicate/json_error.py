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


"""Common errors the the citest.json_contract package."""


from citest.base import JsonSnapshotableEntity


class JsonError(ValueError, JsonSnapshotableEntity):
  """Denotes an error relatived to invalid JSON."""

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make(entity, 'Message', self.message)
    if self.__cause:
      snapshot.edge_builder.make(entity, 'CausedBy', str(self.__cause))

  @property
  def cause(self):
    """An error leading to this error, if any."""
    return self.__cause

  def __init__(self, message, cause=None):
    """Constructor.

    Args:
      message: [string] The error message.
      cause: [error] Optional error that lead to this error.
    """
    self.__cause = cause
    super(JsonError, self).__init__(message)

  def __str__(self):
    return self.message or self.__class__.__name__

  def __eq__(self, error):
    return (self.__class__ == error.__class__
            and self.message == error.message
            and self.__cause == error.cause)
