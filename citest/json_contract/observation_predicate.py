# Copyright 2017 Google Inc. All Rights Reserved.
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

"""Support for applying predicates to Observations.

These predicates mediate between observations and generic ValuePredicates.
Specializations target particular attributes of an observation and
act as a guard to verify that the attribute is set before delegating,
and calls the delegate with the attribute value rather than the Observation.
"""


import logging

from citest.json_predicate import (
    PredicateResult,
    ValuePredicate,
    DICT_MATCHES,
    LIST_MATCHES,
    NOT)



class ObservationPredicateResult(PredicateResult):
  """Specialization of PredicateResult used by ObservationPredicate."""
  @property
  def observation(self):
    """The observation being reported on."""
    return self.__observation

  @property
  def pred(self):
    """The predicate performing the analysis."""
    return self.__pred

  @property
  def pred_result(self):
    """The predicate analysis."""
    return self.__pred_result

  def __init__(self, valid, observation, pred, pred_result, **kwargs):
    super(ObservationPredicateResult, self).__init__(valid, **kwargs)
    self.__observation = observation
    self.__pred = pred
    self.__pred_result = pred_result

  def __str__(self):
    return 'pred={0}, pred_result={1}, observation={2}'.format(
        self.__pred, self.__pred_result, self.__observation)

  def __repr__(self):
    return 'pred={0!r}, pred_result={1!r}, observation={2!r}'.format(
        self.__pred, self.__pred_result, self.__observation)

  def __eq__(self, result):
    return (super(ObservationPredicateResult, self).__eq__(result)
            and self.__pred == result.pred
            and self.__pred_result == result.pred_result
            and self.__observation == result.observation)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(
        entity, 'Predicate', self.__pred)
    snapshot.edge_builder.make_input(
        entity, 'Observation', self.__observation)
    snapshot.edge_builder.make(
        entity, 'Result', self.__pred_result,
        relation=('VALID' if self.__pred_result.valid else 'INVALID'))
    super(ObservationPredicateResult, self).export_to_json_snapshot(
        snapshot, entity)


class ObservationPredicate(ValuePredicate):
  """A placeholder indicating a type of ObservationPredicate.

  ObservationPredicates are ValuePredicates whose value is
  expected to be a json_contract.Observation.
  """
  # pylint: disable=abstract-method
  pass


class NotObservationPredicate(ObservationPredicate):
  """Negates an observation predicate

  This is used to implement "excludes" predicates.
  """

  def __init__(self, pred):
    self.__pred = NOT(pred)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__pred == pred.pred)

  def __call__(self, context, value):
    return self.__pred(context, value)

  def __str__(self):
    return str(self.__pred)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Predicate', self.__pred)


class ObservationErrorPredicate(ObservationPredicate):
  """An observation predicate that mediates the list of Observation.errors."""

  @property
  def pred(self):
    """The predicate delegate that looks at individual errors."""
    return self.__pred

  def __init__(self, pred):
    self.__pred = pred

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__pred == pred.pred)

  def __call__(self, context, value):
    """Implements ValuePredicate interface."""
    observation = value
    if not observation.errors:
      logging.getLogger(__name__).debug(
          'Failing because of observation had no errors')
      return PredicateResult(
          False,
          comment='Automatically fails because observation had no errors.')

    pred_result = self.__pred(context, observation.errors)
    return ObservationPredicateResult(
        pred_result.valid, observation,
        pred=self.__pred, pred_result=pred_result)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Predicate', self.__pred)


class ObservationValuePredicate(ObservationPredicate):
  """An observation predicate that mediates Observation.errors.

  Note that this mediates the entire list of observed objects.
  Therefore the predicate delegates should expect object lists.
  """

  @property
  def pred(self):
    """The ValuePredicate to apply to the observed objects."""
    return self.__pred

  def __init__(self, pred):
    """Constructor.

    Args:
      pred: [ValuePredicate] Predicate to apply to observed object lists.
    """
    super(ObservationValuePredicate, self).__init__()
    self.__pred = pred

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__pred == pred.pred)

  def __str__(self):
    return 'ObservationValuePredicate pred={0}'.format(self.__pred)

  def __repr__(self):
    return 'ObservationValuePredicate pred={0!r}'.format(self.__pred)

  def __call__(self, context, value):
    """Implements ValuePredicate interface."""
    observation = value

    if observation.errors:
      logging.getLogger(__name__).debug(
          'Failing because of observation errors %s', observation.errors)
      return PredicateResult(
          False, comment='Automatically fails because observation failed.')
    pred_result = self.__pred(context, observation.objects)
    return ObservationPredicateResult(
        pred_result.valid, observation,
        pred=self.__pred, pred_result=pred_result)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Predicate', self.__pred)


class ObservationPredicateFactory(object):
  """Factory for creating ObservationPredicates

  This is to provide higher level constructors for predicates
  to pass to an ObservationVerifyResultBuilder.
  """

  def value_list_matches(self, list_pred_args, **kwargs):
    """An ObservationValuePredicate that LIST_MATCHES.

    Args:
      list_pred_args: [list of ValuePredicates] The predicates to apply to
          the observation.values
      kwargs: [kwargs] Passed through the the LIST_MATCHES constructor
    """
    return ObservationValuePredicate(LIST_MATCHES(list_pred_args, **kwargs))

  def value_list_contains(self, pred):
    """Shortcut for expect_value_list_matches where the list is just one pred.

    Args:
      pred: [ValuePredicate] The value predicate to look for in the list.
    """
    return self.value_list_matches([pred])

  def value_list_excludes(self, pred):
    """Shortcut for expect_value_list_matches where the list is just one pred.

    Args:
      pred: [ValuePredicate] The value predicate to look for in the list.
    """
    return NotObservationPredicate(self.value_list_matches([pred]))

  def value_list_path_contains(self, path, pred):
    """Shortcut for finding a particular pattern within some observed value.

    Essentially this results in an ObservationValuePredicate
      that LIST_MATCHES
      with an element whose dictionary contains a |path| matching |pred|.

    Args:
      path: [path] A path to a dictionary element. This can be nested.
         It should comply with json_predicate.PathPredicate syntax.
      pred: [ValuePredicates] The predicates to apply to the observation.values
    """
    return self.value_list_matches([DICT_MATCHES({path: pred})])

  def value_list_path_excludes(self, path, pred):
    """Shortcut for finding a particular pattern within some observed value.

    Essentially this results in an ObservationValuePredicate
      that LIST_MATCHES
      with an element whose dictionary contains a |path| matching |pred|.

    Args:
      path: [path] A path to a dictionary element. This can be nested.
         It should comply with json_predicate.PathPredicate syntax.
      pred: [ValuePredicates] The predicates to apply to the observation.values
    """
    return NotObservationPredicate(
        self.value_list_matches([DICT_MATCHES({path: pred})]))

  def error_list_matches(self, list_pred_args, **kwargs):
    """An ObservationErrorPredicate that LIST_MATCHES.

    Args:
      list_pred_args: [list of ValuePredicates] The predicates to apply to
          the observation.errors
      kwargs: [kwargs] Passed through the the LIST_MATCHES constructor
    """
    return ObservationErrorPredicate(LIST_MATCHES(list_pred_args, **kwargs))

  def error_list_contains(self, pred):
    """Shortcut for error_list_matches where the list is just one pred.

    Args:
      pred: [ValuePredicate] The value predicate to look for in the list.
    """
    return self.error_list_matches([pred])
