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


from ..base.scribe import Scribable

class Observation(Scribable):
  """Tracks details for ObjectObserver and ObservationVerifier.

  Attributes:
    objects: The observed objects.
    errors: Failed PredicateResult objects or other observer errors.
  """
  @property
  def objects(self):
    return self._objects

  @property
  def errors(self):
    return self._errors

  def __init__(self):
    self._objects = []
    self._errors = []
    pass

  def _make_scribe_parts(self, scribe):
    parts = [
      scribe.part_builder.build_output_part('Errors', self._errors),
      scribe.part_builder.build_data_part(
          'Objects', self._objects,
          summary=scribe.make_object_count_summary(self._objects))]
    return parts

  def __str__(self):
    return 'objects={0!r}  errors={1!r}'.format(
      self._objects, ','.join([str(x) for x in self._errors]))

  def __eq__(self, observation):
    if not self.error_lists_equal(self._errors, observation._errors):
      return False

    return self._objects == observation._objects

  def __ne__(self, observation):
    return not self.__eq__(observation)

  def add_error(self, error):
    """Adds an invalid PredicateResult or other error type.

    Args:
      error: A failed PredicateResult or other error type.
    """
    self._errors.append(error)

  def add_object(self, obj):
    """Adds observed object.

    Args:
      obj: The object to add.
    """
    self._objects.append(obj)

  def add_all_objects(self, objs):
    """Adds a list of observed objects.

    Args:
      objs: A list of individual objects to add.
        To add the list as a single object, call add_object.
    """
    self._objects.extend(objs)

  def extend(self, observation):
    """Extend the observation by another call.

    Args:
      observation: The Observation to extend by.
    """
    self._objects.extend(observation._objects)
    self._errors.extend(observation._errors)

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
    for i in range(len(list_a)):
      error_a = list_a[i]
      error_b = list_b[i]
      if isinstance(error_a, Exception):
          if error_a.__class__ != error_b.__class__:
            return False
      else:
        if error_a != error_b:
          return False
    return True


class ObjectObserver(Scribable):
  """Acts as an object source to feed objects into a contract.

  This class requires specialization for specific sources.

  Attributes:
    filter: A predicate, or None, for filtering objects before adding
        them to the Observation.
  """
  @property
  def filter(self):
    return self._filter

  def _make_scribe_parts(self, scribe):
    return [scribe.part_builder.build_mechanism_part('Filter', self._filter)]

  def __init__(self, filter=None):
    """Construct instance.

    Args:
      filter: An optional ValuePredicate. If provided, then use this to filter
          objects as they are collected. Only objects passing the filter will
          be added to observations.
    """
    self._filter = filter

  def filter_all_objects_to_observation(self, objects, observation):
    """Add objects to Observation that comply with the observer's filter.

    Args:
      objects: The list of objects to add.
        Each element will be filtered independently
      observation: The Observation object to add filtered objects to.
    """
    if not self._filter:
      observation.add_all_objects(objects)
      return

    if not isinstance(objects, list):
      objects = [objects]
    for obj in objects:
      obj_result = self._filter(obj)
      if obj_result:
        observation.add_object(obj)

  def collect_observation(self, observation, trace=True):
    """Collect an Observation.

    Args:
      observation: The Observation to collect into.
      trace: If true then debug the details producing the observation.
    """
    raise NotImplementedError('Needs Specialized in ' + self.__class__)
