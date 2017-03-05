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

"""Maps a predicate over each member of a collection of value objects."""


import collections

from ..base import JsonSnapshotableEntity
from .sequenced_predicate_result import SequencedPredicateResult
from . import predicate


class ObjectResultMapAttempt(
    collections.namedtuple('ObjectResultMapAttempt', ['obj', 'result']),
    JsonSnapshotableEntity):
  """Holds a individual value and its result."""

  @property
  def summary(self):
    """Human readable summary of applying the map for reporting purposes."""
    return self.result.summary

  def __str__(self):
    return '{0} -> {1}'.format(self.obj, self.result)

  def __eq__(self, attempt):
    return (self.__class__ == attempt.__class__
            and self.obj == attempt.obj
            and self.result == attempt.result)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    result_summary = '{name} {valid}'.format(
        name=self.obj.__class__.__name__, valid=self.result.valid)
    builder.make_input(entity, 'Mapped Object', self.obj, format='json')
    builder.make(entity, 'Result', self.result,
                 relation=builder.determine_valid_relation(self.result),
                 summary=result_summary)


class MapPredicateResultBuilder(object):
  """Builds MapPredicateResult instances."""

  def __init__(self, pred):
    self.__pred = pred
    self.__obj_list = []
    self.__all_results = []
    self.__good_map = []
    self.__bad_map = []

  def apply_object(self, obj):
    """Applies the predicate to an element value."""
    result = self.__pred(obj)
    self.add_result(obj, result)
    return result

  def add_result(self, obj, result):
    """Adds the result from an element value."""
    self.__obj_list.append(obj)
    self.__all_results.append(result)
    if result:
      self.__good_map.append(ObjectResultMapAttempt(obj, result))
    else:
      self.__bad_map.append(ObjectResultMapAttempt(obj, result))

  def build(self, valid):
    """Creates the MapPredicateResult instance specified by this builder."""
    return MapPredicateResult(
        valid=valid, pred=self.__pred,
        obj_list=self.__obj_list, all_results=self.__all_results,
        good_map=self.__good_map, bad_map=self.__bad_map)


class MapPredicateResult(SequencedPredicateResult):
  """PredicateResult when mapping a predicate over a collection of values."""

  @property
  def good_object_result_mappings(self):
    """The subset of mappings that were valid."""
    return self.__good_map

  @property
  def bad_object_result_mappings(self):
    """The subset of mappings that were invalid."""
    return self.__bad_map

  @property
  def obj_list(self):
    """The list of objects we mapped the predicate over."""
    return self.__obj_list

  @staticmethod
  def __map_attempt_to_entity(attempt, snapshot):
    """Helper method exporting a snapshot entity for an individual attempt."""

    attempt_entity = snapshot.new_entity()
    attempt_entity.add_metadata('class', attempt.__class__)
    builder = snapshot.edge_builder
    builder.make_input(attempt_entity, 'Object', attempt.obj,
                       format='json',
                       summary=attempt.obj.__class__)
    builder.make(attempt_entity, 'Result Map', attempt.result,
                 relation=builder.determine_valid_relation(attempt.result),
                 summary=attempt.summary)
    return attempt_entity

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    func = lambda l: [self.__map_attempt_to_entity(e, snapshot) for e in l]
    builder = snapshot.edge_builder
    builder.make_input(entity, 'Object List', self.__obj_list,
                       format='json',
                       summary=builder.object_count_to_summary(
                           self.__obj_list, subject='mapped object'))
    edge = builder.make(entity, 'Good Mappings',
                        func(self.__good_map),
                        summary=builder.object_count_to_summary(
                            self.__good_map, subject='valid mapping'))
    if self.__good_map:
      edge.add_metadata('relation', 'VALID')
    edge = builder.make(entity, 'Bad Mappings',
                        func(self.__bad_map),
                        summary=builder.object_count_to_summary(
                            self.__bad_map, subject='invalid mapping'))
    if self.__bad_map:
      edge.add_metadata('relation', 'INVALID')
    super(MapPredicateResult, self).export_to_json_snapshot(snapshot, entity)

  def __init__(self, valid, pred, obj_list, all_results,
               good_map, bad_map, **kwargs):
    # pylint: disable=too-many-arguments
    self.__obj_list = obj_list
    self.__good_map = good_map
    self.__bad_map = bad_map

    # When we snapshot, dont show all the results
    # These are redundant with the good/bad breakout that we'll add.
    # Having both can get pretty large.
    super(MapPredicateResult, self).__init__(
        valid=valid, pred=pred, results=all_results,
        keep_results_attribute_in_snapshot=False, **kwargs)

  def __eq__(self, result):
    return (super(MapPredicateResult, self).__eq__(result)
            and self.__obj_list == result.obj_list
            and self.__good_map == result.good_object_result_mappings
            and self.__bad_map == result.bad_object_result_mappings)

  def clone_with_source(self, source, base_target_path, base_value_path):
    """Implements CloneableWithNewSource interface."""
    builder = MapPredicateResultBuilder(self.pred)

    for index, orig in enumerate(self.results):
      if isinstance(orig, predicate.CloneableWithNewSource):
        result = orig.clone_with_source(source=source,
                                        base_target_path=base_target_path,
                                        base_value_path=base_value_path)
      else:
        result = orig
      builder.add_result(self.__obj_list[index], result)
    return builder.build(self.valid)


class MapPredicate(predicate.ValuePredicate):
  """Applies a predicate to all elements of a list or a non-list object.

  The Map has a min/max range that determine when results should be valid.
  If the max is None then there is no upper bound.
  """
  @property
  def pred(self):
    """The predicate to map over the individual values."""
    return self.__pred

  def __init__(self, pred, min=1, max=None, **kwargs):
    """Constructor.

    Args:
      pred: [ValuePredicate] The predicate to map.
      min: [int] The minimum number of values the predicate is expected
         to return true for.
      max: [int] The maximum number of values the predicate is expected
         to return true for (or None for no upper bound).

      See base class (ValuePredicate) for additional kwargs.
    """
    # pylint: disable=redefined-builtin
    self.__pred = pred
    self.__min = min
    self.__max = max
    super(MapPredicate, self).__init__(**kwargs)

  def __str__(self):
    return 'Map({0!r})'.format(self.__pred)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__pred == pred.pred)

  def __call__(self, context, obj):
    """Determine if object or its members match the expected fields.

    Args:
      obj: The JSON object to match.

    Returns:
      MapPredicateResult of pred applied to all the objects.
    """
    all_results = []
    good_map = []
    bad_map = []

    if not isinstance(obj, list) and obj != None:
      obj_list = [obj]
    else:
      obj_list = obj

    if obj_list != None:
      for elem in obj_list:
        result = self.__pred(context, elem)
        all_results.append(result)
        if result:
          good_map.append(ObjectResultMapAttempt(elem, result))
        else:
          bad_map.append(ObjectResultMapAttempt(elem, result))

    the_min = context.eval(self.__min)
    the_max = context.eval(self.__max)
    valid = not (the_min != None and len(good_map) < the_min
                 or the_max != None and len(good_map) > the_max)
    return MapPredicateResult(
        valid=valid, pred=self.__pred,
        obj_list=obj_list,
        all_results=all_results,
        good_map=good_map,
        bad_map=bad_map)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    builder.make_mechanism(entity, 'Mapped Predicate', self.__pred,
                           summary=self.__pred.__class__)
    builder.make_control(entity, 'Min', self.__min)
    builder.make_control(entity, 'Max', self.__max)
