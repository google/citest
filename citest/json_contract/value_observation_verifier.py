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

# pylint: disable=missing-docstring
# pylint: disable=redefined-builtin

import logging

from ..json_predicate import binary_predicate
from ..json_predicate import cardinality_predicate
from ..json_predicate import logic_predicate
from ..json_predicate import path_predicate
from ..json_predicate import predicate
from . import observation_verifier as ov
from . import observation_failure as of


class ValueObservationVerifierBuilder(ov.ObservationVerifierBuilder):
  def __init__(self, title, strict=False):
    """Constructor.

    Args:
      title: [string] The name of the verifier for reporting purposes.
      strict: [bool] Whether the verifier is strict or not.
         Strict verifiers require all the objects to satisfy all the
         constraints.  Non-strict verifiers require all the constraints
         to be satisfied by at least one object (but not necessarily the same),
         and some objects may not satisfy any constraints at all.
    """
    super(ValueObservationVerifierBuilder, self).__init__(title)
    self.__strict = strict
    self.__constraints = []

  def __eq__(self, builder):
    """Specializes interface."""
    # pylint: disable=protected-access
    return (super(ValueObservationVerifierBuilder, self).__eq__(builder)
            and self.__strict == builder.__strict
            and self.__constraints == builder.__constraints)

  def _do_build_generate(self, dnf_verifiers):
    """Constructs the actual instance."""
    return ValueObservationVerifier(
        title=self.title,
        dnf_verifiers=dnf_verifiers,
        constraints=self.__constraints,
        strict=self.__strict)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Strict', self.__strict)
    if len(self.__constraints) == 1:
      # Optimize model for single-element list
      snapshot.edge_builder.make_control(
          entity, 'Constraint', self.__constraints[0])
    else:
      snapshot.edge_builder.make_control(
          entity, 'Constraints', self.__constraints)

    super(ValueObservationVerifierBuilder, self).export_to_json_snapshot(
        snapshot, entity)

  def add_constraint(self, constraint):
    if not isinstance(constraint, predicate.ValuePredicate):
      raise TypeError('{0} is not predicate.ValuePredicate'.format(
          constraint.__class__))
    self.__constraints.append(constraint)
    return self

  def contains_path_match(self, path, match_spec, min=1, max=None,
                          **kwargs):
    if isinstance(match_spec, list):
      enumerate_terminals = kwargs.pop('enumerate_terminals', False)
      return self.contains_path_pred(
          path, binary_predicate.LIST_MATCHES(match_spec), min, max,
          enumerate_terminals=enumerate_terminals, **kwargs)
    else:
      return self.contains_path_pred(
          path, binary_predicate.DICT_MATCHES(match_spec), min, max)

  def contains_path_value(self, path, value, min=1, max=None):
    return self.contains_path_pred(
        path, binary_predicate.CONTAINS(value), min, max)

  def contains_path_eq(self, path, value, min=1, max=None):
    return self.contains_path_pred(
        path, binary_predicate.EQUIVALENT(value), min, max)

  def contains_path_pred(self, path, pred, min=1, max=None, **kwargs):
    enumerate_terminals = kwargs.pop('enumerate_terminals', True)
    self.add_constraint(
        cardinality_predicate.CardinalityPredicate(
            path_predicate.PathPredicate(
                path, pred, enumerate_terminals=enumerate_terminals),
            min=min, max=max))
    return self

  def contains_pred_list(self, pred_list, min=1, max=None):
    conjunction = logic_predicate.AND(pred_list)
    self.add_constraint(
        cardinality_predicate.CardinalityPredicate(
            conjunction, min=min, max=max))
    return self

  def contains_match(self, match_spec, min=1, max=None):
    if isinstance(match_spec, list):
      constraint = binary_predicate.LIST_MATCHES(match_spec)
      self.add_constraint(
          cardinality_predicate.CardinalityPredicate(
              path_predicate.PathPredicate(
                  '', constraint, enumerate_terminals=False),
              min=min, max=max))
    else:
      self.add_constraint(
          cardinality_predicate.CardinalityPredicate(
              binary_predicate.DICT_MATCHES(match_spec), min=min, max=max))
    return self

  def excludes_path_pred(self, path, pred, max=0, **kwargs):
    enumerate_terminals = kwargs.pop('enumerate_terminals', True)
    self.add_constraint(
        cardinality_predicate.CardinalityPredicate(
            path_predicate.PathPredicate(
                path, pred, enumerate_terminals=enumerate_terminals),
            min=0, max=max))
    return self

  def excludes_path_match(self, path, match_spec, max=0):
    if isinstance(match_spec, list):
      return self.excludes_path_pred(
          path, binary_predicate.LIST_MATCHES(match_spec), max,
          enumerate_terminals=False)
    else:
      return self.excludes_path_pred(
          path, binary_predicate.DICT_MATCHES(match_spec), max)

  def excludes_path_value(self, path, value, max=0):
    return self.excludes_path_pred(path, binary_predicate.CONTAINS(value),
                                   max)

  def excludes_path_eq(self, path, value, max=0):
    return self.excludes_path_pred(
        path, binary_predicate.EQUIVALENT(value), max)

  def excludes_match(self, match_spec, max=0):
    if isinstance(match_spec, list):
      constraint = binary_predicate.LIST_MATCHES(match_spec)
      self.add_constraint(
          cardinality_predicate.CardinalityPredicate(
              path_predicate.PathPredicate(
                  '', constraint, enumerate_terminals=False),
              min=0, max=max))
    else:
      self.add_constraint(
          cardinality_predicate.CardinalityPredicate(
              binary_predicate.DICT_MATCHES(match_spec), min=0, max=max))
    return self

  def excludes_pred_list(self, pred_list, max=0):
    conjunction = logic_predicate.AND(pred_list)
    self.add_constraint(
        cardinality_predicate.CardinalityPredicate(
            conjunction, min=0, max=max))
    return self


class ValueObservationVerifier(ov.ObservationVerifier):
  @property
  def constraints(self):
    return self.__constraints

  @property
  def strict(self):
    return self.__strict

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Strict', self.__strict)
    snapshot.edge_builder.make_control(
        entity, 'Constraints', self.__constraints)
    super(ValueObservationVerifier, self).export_to_json_snapshot(
        snapshot, entity)

  def __str__(self):
    return '{0} constraints={1} strict={2}'.format(
        super(ValueObservationVerifier, self).__str__(),
        [str(x) for x in self.__constraints],
        self.__strict)

  def __init__(self, title, **kwargs):
    """Construct instance.

    Args:
      title: The name of the verifier for reporting purposes only.
      dnf_verifiers: A list of lists of jc.ObservationVerifier where the outer
          list are OR'd together and the inner lists are AND'd together
          (i.e. disjunctive normal form).
      constraints: A list of jc.ValuePredicate to apply to the
          observation object list.
      strict: If True then the verifier requires all the observed elements to
          satisfy all the constraints (including future added constraints).
          Otherwise if False then the verifier requires each of the constraints
          to be satisfied by at least one object. Not necessarily the same
          object, nor does any object have to satisfy even one constraint.

       See base class (ov.ObservationVerifier) for additional kwargs.
    """
    self.__strict = kwargs.pop('strict', False)
    constraints = kwargs.pop('constraints', None)
    self.__constraints = constraints
    self.__value_constraints = []
    self.__observation_constraints = []
    for constraint in constraints:
      if isinstance(constraint, ov.ObservationVerifier):
        self.__observation_constraints.append(constraint)
      else:
        self.__value_constraints.append(constraint)
    super(ValueObservationVerifier, self).__init__(title, **kwargs)

  def __call__(self, context, observation):
    valid = True
    final_builder = ov.ObservationVerifyResultBuilder(observation)

    for constraint in self.__observation_constraints:
      result = constraint(context, observation)
      valid = valid and result
      final_builder.add_observation_verify_result(result)

    if observation.errors:
      if self.__value_constraints:
        valid = False
        logging.getLogger(__name__).debug(
            'Failing because of observation errors %s', observation.errors)
        error = of.ObservationFailedError(observation.errors)
        final_builder.add_observation_verify_result(
            ov.ObservationVerifyResult(
                valid=False, observation=observation,
                good_results=[], bad_results=[error],
                failed_constraints=[self.__value_constraints]))
      return final_builder.build(valid)

    all_objects = observation.objects
    if not all_objects:
      # If we have no objects, then we will not iterate over anything
      # so will not check any contracts.
      # Instead, add a None object to the list so we'll check each contract
      # against None to see if it is satisfied.
      logging.getLogger(__name__).debug(
          'Verifying object None to indicate no objects at all.')
      object_list = [None]
    else:
      object_list = all_objects

    # Every constraint must be satisfied by at least one object.
    # If strict then every object must be verified by at least one
    # constraint.
    final_builder = ov.ObservationVerifyResultBuilder(observation)

    for constraint in self.__value_constraints:
      logging.getLogger(__name__).debug('Verifying constraint=%s',
                                        constraint)

      if isinstance(constraint, path_predicate.ProducesPathPredicateResult):
        constraint_result = constraint(context, object_list)
      else:
        constraint_result = (
            path_predicate.PathPredicate('', constraint)(context, object_list))
      if not constraint_result:
        logging.getLogger(__name__).debug('FAILED constraint')
        valid = False

      final_builder.add_path_predicate_result(constraint_result)

    if valid and self.__strict:
      len_validated = len(final_builder.validated_object_set)
      len_objects = len(object_list)
      valid = len_validated == len_objects

      if not valid:
        comment = ('Strict verifier "{0}" confirmed {1} of {2} objects.'
                   .format(self.title, len_validated, len_objects))
        logging.getLogger(__name__).info(comment)

    return final_builder.build(valid)
