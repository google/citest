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


"""Observers make observations that are a collection of data to be verified."""


from citest.base import JsonSnapshotableEntity

class Observation(JsonSnapshotableEntity):
  """Tracks details for ObjectObserver and ObservationVerifier."""

  @property
  def objects(self):
    """The observed objects."""
    return self.__objects

  @property
  def errors(self):
    """Failed PredicateResult objects or other observer errors."""
    return self.__errors

  def __init__(self):
    self.__objects = []
    self.__errors = []

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    edge = builder.make(entity, 'Errors', self.__errors)
    if self.__errors:
      edge.add_metadata('relation', 'ERROR')
    builder.make_data(entity, 'Objects', self.__objects,
                      format='json',
                      summary=builder.object_count_to_summary(self.__objects))

  def __str__(self):
    return 'objects={0!r}  errors={1!r}'.format(
        self.__objects, ','.join([str(x) for x in self.__errors]))

  def __eq__(self, observation):
    if not self.error_lists_equal(self.__errors, observation.errors):
      return False

    return self.__objects == observation.objects

  def __ne__(self, observation):
    return not self.__eq__(observation)

  def add_error(self, error):
    """Adds an invalid PredicateResult or other error type.

    Args:
      error: A failed PredicateResult or other error type.
    """
    self.__errors.append(error)

  def add_object(self, obj):
    """Adds observed object.

    Args:
      obj: The object to add.
    """
    self.__objects.append(obj)

  def add_all_objects(self, objs):
    """Adds a list of observed objects.

    Args:
      objs: A list of individual objects to add.
        To add the list as a single object, call add_object.
    """
    self.__objects.extend(objs)

  def extend(self, observation):
    """Extend the observation by another call.

    Args:
      observation: The Observation to extend by.
    """
    self.__objects.extend(observation.objects)
    self.__errors.extend(observation.errors)

  @staticmethod
  def error_lists_equal(list_a, list_b):
    """Compare two lists of errors being equal to one another.

    This is sensitive to the ordering. If the corresponding elements
    are exceptions then only compare the class (because exceptions dont
    implement value __eq__), otherwise do a full equal check.

    Args:
      list_a: A list of objects, each of which is PredicateResult or Exception.
      list_b: A list of objects, each of which is PredicateResult or Exception.
    Returns:
      True if the lists are pairwise equivalent, or False if not.
   """
    if len(list_a) != len(list_b):
      return False
    for i, error_a in enumerate(list_a):
      error_b = list_b[i]
      if isinstance(error_a, Exception):
        if error_a.__class__ != error_b.__class__:
          return False
      else:
        if error_a != error_b:
          return False
    return True


class ObjectObserver(JsonSnapshotableEntity):
  """Acts as an object source to feed objects into a contract.

  This class requires specialization for specific sources.
  """
  @property
  def filter(self):
    """A predicate for filtering objects before adding them to the Observation.

    None indicates there is no filter (add all objects).
    """
    return self.__filter

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Filter', self.__filter)

  def __init__(self, filter=None):
    """Construct instance.

    Args:
      filter: An optional ValuePredicate. If provided, then use this to filter
          objects as they are collected. Only objects passing the filter will
          be added to observations.
    """
    self.__filter = filter

  def filter_all_objects_to_observation(self, context, objects, observation):
    """Add objects to Observation that comply with the observer's filter.

    Args:
      context: The execution context to filter within.
      objects: The list of objects to add.
        Each element will be filtered independently
      observation: The Observation object to add filtered objects to.
    """
    if not self.__filter:
      observation.add_all_objects(objects)
      return

    if not isinstance(objects, list):
      objects = [objects]
    for obj in objects:
      obj_result = self.__filter(context, obj)
      if obj_result:
        observation.add_object(obj)

  def collect_observation(self, context, observation):
    """Collect an Observation.

    Args:
      observation: The Observation to collect into.
      context: Runtime execution context.
    """
    raise NotImplementedError('Needs Specialized in ' + self.__class__)
