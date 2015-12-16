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


from ..base.scribe import Scribable
from ..base import JsonSnapshotable


class JsonError(ValueError, Scribable, JsonSnapshotable):
  """Denotes an error relatived to invalid JSON."""

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.new(entity, 'Message', self.message)
    if self.__cause:
      snapshot.edge_builder.make(entity, 'CausedBy', str(self.__cause))

  def _make_scribe_parts(self, scribe):
    parts = [scribe.build_part('Message', self.message)]
    if self.__cause:
      parts.append(scribe.build_part('CausedBy', self.__cause))
    return parts

  def __init_(self, message, cause=None):
    super(JsonError, self).__init__(message)
    self.__cause = cause

  def __str__(self):
    return self.message or self.__class__.__name__

  def __eq__(self, error):
    return (self.__class__ == error.__class__
            and self.message == error.message
            and self.__cause == error.__cause)


        
