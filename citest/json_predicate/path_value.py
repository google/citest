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


"""Track the accumulation of Path/Value pairs found."""

import collections
from ..base import JsonSnapshotableEntity

# Denotes the seperator used when specifying paths to JSON attributes
# in an object hierarchy.
PATH_SEP = '/'


def build_path(*parts):
  return PATH_SEP.join(parts)


class PathValue(collections.namedtuple('PathValue', ['path', 'value']),
                JsonSnapshotableEntity):
  """A path, value pair.

  Attributes:
    path: The slash-delimited string of field names to traverse to the value.
    value: The JSON object value at the path leaf.
      The object may itself be compound but is all the path specified.
  """
  def __str__(self):
    return '"{0}"={1!r}'.format(self.path, self.value)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Path', self.path)
    snapshot.edge_builder.make_data(entity, 'Value', self.value,
                                    format='json')
