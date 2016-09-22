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


"""Provides citest execution context state for use when writing tests.

This is intended to share data between the caller setting up a test
and the actual execution of the test, which is decoupled from the caller.
The context can also be used to collect runtime state and information that is
needed later in the tests execution or evaluation.
"""

from .snapshot import JsonSnapshotable


class ExecutionContext(JsonSnapshotable):
  """Execution context"""

  def __init__(self, **kwargs):
    """Constructor.

    Args:
      kwargs: name=value Initial snapshotable attribute name/value pairs.
    """
    self.__external = dict(kwargs or {})
    self.__internal = {}

  def __contains__(self, key):
    """Determine if key is a known attribute."""
    return key in self.__internal or key in self.__external

  def __delitem__(self, key):
    """Remove keys if they exist."""
    if key in self.__internal:
      del self.__internal[key]
    elif key in self.__external:
      del self.__external[key]

  def __setitem__(self, key, value):
    self.set_snapshotable(key, value)

  def __getitem__(self, key):
    return (self.__internal[key]
            if key in self.__internal
            else self.__external[key])

  def clear_key(self, key):
    """Remove key whether or not it exists."""
    if key in self.__internal:
      del self.__internal[key]
    elif key in self.__external:
      del self.__external[key]

  def get(self, key, default_value):
    """Lookup value of attribute, or default_value if attribute isn't known."""
    return (self.__internal[key]
            if key in self.__internal
            else self.__external[key] if key in self.__external
            else default_value)

  def set_snapshotable(self, key, value):
    """Set attribute key=value, making it appear in snapshots."""
    if not key:
      KeyError('Key cannot be empty')
    if key in self.__internal:
      KeyError('{0} is already an internal key'.format(key))
    self.__external[key] = value

  def set_internal(self, key, value):
    """Set attribute key=value, but not making it appear in snapshots."""
    if not key:
      KeyError('Key cannot be empty')
    if key in self.__external:
      KeyError('{0} is already a snapshotable key'.format(key))
    self.__internal[key] = value

  def add_snapshotable(self, key, value):
    """Set attribute key=value, making it appear in snapshots.

    Raises:
      KeyError if key is already an attribute.
    """
    if not key:
      KeyError('Key cannot be empty')
    if key in self.__internal:
      KeyError('{0} is already an internal key'.format(key))
    if key in self.__external:
      KeyError('{0} already exists'.format(key))
    self.__external[key] = value

  def add_internal(self, key, value):
    """Set attribute key=value, but not making it appear in snapshots.

    Raises:
      KeyError if key is already an attribute.
    """
    if not key:
      KeyError('Key cannot be empty')
    if key in self.__external:
      KeyError('{0} is already a snapshotable key'.format(key))
    if key in self.__internal:
      KeyError('{0} already exists'.format(key))
    self.__internal[key] = value

  def snapshotable_items(self):
    """Return list of snapshotable (name, value) tuples."""
    return self.__external.items()

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    for key, value in self.__external.items():
      snapshot.edge_builder.make_data(entity, key, value)

  def eval(self, value):
    """Evaluate value in this ExecutionContext.

    Args:
      value: [any] The value to evaluate.

    Returns:
      The actual value.
    """
    if isinstance(value, list):
      return [self.eval(elem) for elem in value]
    elif isinstance(value, dict):
      return {key: self.eval(data) for key, data in value.items()}
    elif callable(value):
      return value(self)
    else:
      return value
