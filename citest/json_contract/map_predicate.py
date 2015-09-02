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


import collections

from ..base.scribe import Scribable
from . import predicate


class ObjectResultMapAttempt(
      collections.namedtuple('ObjectResultMapAttempt', ['obj', 'result']),
      Scribable):
  @property
  def summary(self):
    return self.result.summary

  def __str__(self):
    return '{0} -> {1}'.format(self.obj, self.result)

  def __eq__(self, attempt):
    return (self.__class__ == attempt.__class__
            and self.obj == attempt.obj
            and self.result == attempt.result)

  def _make_scribe_parts(self, scribe):
    result_summary = '{name} {valid}'.format(
        name=self.obj.__class__.__name__, valid=self.result.valid)
    return [scribe.part_builder.build_input_part(
               'Mapped Object', self.obj, summary=self.obj.__class__),
            scribe.part_builder.build_output_part(
               'Result', self.result, summary=result_summary)]


class MapPredicateResultBuilder(object):
  def __init__(self, pred):
    self._pred = pred
    self._obj_list = []
    self._all_results = []
    self._good_map = []
    self._bad_map = []

  def apply_object(self, obj):
    result = self._pred(obj)
    self.add_result(obj, result)
    return result

  def add_result(self, obj, result):
    self._obj_list.append(obj)
    self._all_results.append(result)
    if result:
      self._good_map.append(ObjectResultMapAttempt(obj, result))
    else:
      self._bad_map.append(ObjectResultMapAttempt(obj, result))

  def build(self, valid):
    return MapPredicateResult(
        valid=valid, pred=self._pred,
        obj_list=self._obj_list, all_results=self._all_results,
        good_map=self._good_map, bad_map=self._bad_map)


class MapPredicateResult(predicate.CompositePredicateResult):
  @property
  def good_object_result_mappings(self):
    return self._good_map

  @property
  def bad_object_result_mappings(self):
    return self._bad_map

  @property
  def obj_list(self):
    return self._obj_list

  @staticmethod
  def _render_mapping(out, result_map_attempt):
    scribe = out.scribe
    parts = [
      scribe.part_builder.build_input_part(
        name='Object',
        value=result_map_attempt.obj,
        summary=result_map_attempt.obj.__class__),

      scribe.part_builder.build_output_part(
        name='Result Map',
        value=result_map_attempt.result,
        summary=result_map_attempt.summary)]

    scribe.render_parts(out, parts)


  def _make_scribe_parts(self, scribe):
    parts = [
      scribe.part_builder.build_input_part(
          name='Object List', value=self._obj_list,
          summary=scribe.make_object_count_summary(
              self._obj_list, subject='mapped object')),

      scribe.part_builder.build_output_part(
        name='Good Mappings', value=self._good_map,
        renderer=self._render_mapping,
        summary=scribe.make_object_count_summary(
            self._good_map, subject='valid mapping')),

      scribe.part_builder.build_output_part(
        name='Bad Mappings', value=self._bad_map,
        renderer=self._render_mapping,
        summary=scribe.make_object_count_summary(
            self._bad_map, subject='invalid mapping'))]

    inherited = super(MapPredicateResult, self)._make_scribe_parts(scribe)
    return parts + inherited

  def __init__(self, valid, pred, obj_list, all_results,
               good_map, bad_map, comment=None):
    super(MapPredicateResult, self).__init__(
        valid=valid, pred=pred, results=all_results, comment=comment)
    self._obj_list = obj_list
    self._good_map = good_map
    self._bad_map = bad_map

  def __eq__(self, result):
    return (super(MapPredicateResult, self).__eq__(result)
            and self._obj_list == result._obj_list
            and self._good_map == result._good_map
            and self._bad_map == result._bad_map)

class MapPredicate(predicate.ValuePredicate):
  """Applies a predicate to all elements of a list or a non-list object.

  The Map has a min/max range that determine when results should be valid.
  If the max is None then there is no upper bound.
  """
  @property
  def pred(self):
    return self._pred

  def __init__(self, pred, min=1, max=None):
    self._pred = pred
    self._min = min
    self._max = max

  def __str__(self):
    return 'Map({0!r})'.format(self._pred)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self._pred == pred._pred)

  def __call__(self, obj):
    """Determine if object or its members match the expected fields.

    Args:
      obj: The JSON object to match.

    Returns:
      MapPredicateResult of pred applied to all the objects.
    """
    all_results  = []
    good_map = []
    bad_map = []

    if not isinstance(obj, list) and obj != None:
      obj_list = [obj]
    else:
      obj_list = obj

    if obj_list != None:
      for elem in obj_list:
        result = self._pred(elem)
        all_results.append(result)
        if result:
          good_map.append(ObjectResultMapAttempt(elem, result))
        else:
          bad_map.append(ObjectResultMapAttempt(elem, result))

    valid = not (self._min != None and len(good_map) < self._min
                 or self._max != None and len(good_map) > self._max)
    return MapPredicateResult(
        valid=valid, pred=self._pred,
        obj_list=obj_list,
        all_results=all_results,
        good_map=good_map,
        bad_map=bad_map)

  def _make_scribe_parts(self, scribe):
    part_builder = scribe.part_builder
    return [part_builder.build_mechanism_part(
                'Mapped Predicate', self._pred, summary=self._pred.__class__),
            scribe.build_part('Min', self._min, relation=part_builder.CONTROL),
            scribe.build_part('Max', self._max, relation=part_builder.CONTROL)]
