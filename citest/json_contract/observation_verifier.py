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


"""Support for verifying Observations are consistent with constraints."""


import logging

from ..base import JsonSnapshotableEntity
from ..json_predicate import map_predicate
from ..json_predicate import predicate

class ObservationVerifyResultBuilder(object):
  @property
  def validated_object_set(self):
    return self.__valid_obj_set

  @property
  def observation(self):
    return self.__observation

  @property
  def failed_constraints(self):
    return self.__failed_constraints

  def __init__(self, observation):
    self.__observation = observation
    self.__failed_constraints = []

    # _valid_obj_map is a tuple (object, [list of valid PredicateResult on it])
    # as different constraints look at the objects in the observation, they
    # build up this map with the results to get all the reasons why a
    # particular observed object is considered good because the top-level
    # constraints form a disjunction.
    self.__valid_obj_map = []

    # The _valid_obj_set is a set of objects meeting constriants that verify
    # them. All we need is one reason to think something is good.
    self.__valid_obj_set = []  # Cannot be a set because it is unhashable.
    self.__good_results = []
    self.__bad_results = []

  def __add_valid_object_constraint(self, entry):
    obj = entry.obj
    result = entry.result
    for e in self.__valid_obj_map:
      if e[0] == obj:
        e[1].append(result)
        return

    self.__valid_obj_set.append(obj)
    self.__valid_obj_map.append((obj, [result]))

  def add_path_predicate_result(self, has_path_pred_result):
    """Add the contents of a PathPredicateResult.

    Args:
      has_path_pred_result: [HasPathPredicateResult]  The PredicateResult
          verified implements HasPathPredicateResult. It indicates which
          particular values were good and bad. The constraint being verified
          is the predicate bound to the result.
    """
    path_pred_result = has_path_pred_result.path_predicate_result
    good = path_pred_result.valid_candidates
    attempts = [map_predicate.ObjectResultMapAttempt(
        elem.path_value.value, elem.result) for elem in good]
    self.__good_results.extend(attempts)
    for entry in attempts:
      self.__add_valid_object_constraint(entry)

    failures = path_pred_result.invalid_candidates
    self.__bad_results.extend(
        [map_predicate.ObjectResultMapAttempt(elem.path_value.value,
                                              elem.result)
         for elem in failures])

    if not has_path_pred_result:
      self.add_failed_constraint(has_path_pred_result.pred)
    return self

  def add_map_result(self, map_result):
    """Add the contents of a MapPredicateResult.

    Args:
      map_result: [MapPredicateResult]  Indicates which particular values
      were good and bad. The constraint being verified is the predicate
      bound to the result.
    """
    good_results = map_result.good_object_result_mappings
    self.__good_results.extend(good_results)
    bad_results = map_result.bad_object_result_mappings
    self.__bad_results.extend(bad_results)

    if not good_results:
      self.add_failed_constraint(map_result.pred)
      return
    for entry in good_results:
      self.__add_valid_object_constraint(entry)
    return self

  def add_failed_constraint(self, pred):
    """Add a failed constraint.

    Args:
      pred: [ValuePredicate] A constraint that was not verified. This is either
         because it had no matching objects, or was strict and had some non-
         matching objects.
    """
    self.__failed_constraints.append(pred)
    return self

  def add_observation_verify_result(self, result):
    """Fuses results from another ObservationVerifyResult.

    This is used by composite verifiers that might be a disjunction of
    different clauses, each of which had done its own indepenent verification.

    Args:
      result: [ObservationVerifyResult] The result to fuse into this one.
    """
    if self.__observation != result.observation:
      raise ValueError("Observations differ.")

    self.__good_results.extend(result.good_results)
    self.__bad_results.extend(result.bad_results)
    self.__failed_constraints.extend(result.failed_constraints)
    return self

  def build(self, valid):
    """Create the specified ObservationVerifyResult."""
    return ObservationVerifyResult(
        valid=valid, observation=self.__observation,
        good_results=self.__good_results,
        bad_results=self.__bad_results,
        failed_constraints=self.__failed_constraints)


class ObservationVerifyResult(predicate.PredicateResult):
  """Tracks details from verifying a contract."""

  @property
  def observation(self):
    """observer.Observation for the observer providing the objects."""
    return self.__observation

  @property
  def good_results(self):
    """List of (obj, PredicateResult)."""
    return self.__good_results

  @property
  def bad_results(self):
    """List of (obj, PredicateResult)."""
    return self.__bad_results

  @property
  def failed_constraints(self):
    """List of (constraint, PredicateResult) for constraints with no objects.
    """
    return self.__failed_constraints

  @property
  def enumerated_summary_message(self):
    """Variation of summary_messages with bulleted list (one per indented line).
    """
    results = self.__good_results if self.valid else self.__bad_results
    if not results:
      return ''

    return '  * {0}'.format(
        '\n  * '.join([elem.summary
                       if hasattr(elem, 'summary') and elem.summary
                       else str(elem)
                       for elem in results]))

  def __init__(self, valid, observation,
               good_results, bad_results, failed_constraints,
               **kwargs):
    self.__observation = observation
    self.__good_results = good_results
    self.__bad_results = bad_results
    self.__failed_constraints = failed_constraints
    super(ObservationVerifyResult, self).__init__(valid, **kwargs)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    super(ObservationVerifyResult, self).export_to_json_snapshot(
        snapshot, entity)
    builder = snapshot.edge_builder
    builder.make_input(entity, 'Observation', self.__observation)
    if self.__failed_constraints != []:
      builder.make(entity, 'Failed Constraints', self.__failed_constraints)
    if self.__good_results != []:
      edge = builder.make(entity, 'Good Results', self.__good_results)
      if self.__good_results:
        edge.add_metadata('relation', 'VALID')
    if self.__bad_results != []:
      edge = builder.make(entity, 'Bad Results', self.__bad_results)
      if self.__bad_results:
        edge.add_metadata('relation', 'INVALID')

  def __str__(self):
    return '{0} Observed {1} good and {2} bad.'.format(
        super(ObservationVerifyResult, self).__str__(),
        len(self.__good_results), len(self.__bad_results))

  def __repr__(self):
    return ('{0} observation={1!r}'
            '  good_results={2!r}'
            '  bad_results={3!r}'.format(
                super(ObservationVerifyResult, self).__str__(),
                self.__observation,
                self.__good_results,
                self.__bad_results))

  def __eq__(self, state):
    return (super(ObservationVerifyResult, self).__eq__(state)
            and self.__observation == state.observation
            and self.__good_results == state.good_results
            and self.__bad_results == state.bad_results
            and self.__failed_constraints == state.failed_constraints)


class ObservationVerifier(predicate.ValuePredicate):
  @property
  def dnf_verifiers(self):
    return self.__dnf_verifiers

  @property
  def title(self):
    return self.__title

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    entity.add_metadata('_title', self.__title)
    disjunction = self.__dnf_verifiers
    builder = snapshot.edge_builder
    builder.make(entity, 'Title', self.__title)
    if not disjunction:
      builder.make_control(entity, 'Verifiers', None)
      return

    all_conjunctions = []
    for conjunction in disjunction:
      if len(conjunction) == 1:
        # A special case to optimize the report to remove the conjunction
        # wrapper since there is only one component anyway
        all_conjunctions.append(snapshot.make_entity_for_object(conjunction[0]))
      else:
        conjunction_entity = snapshot.new_entity(summary='AND predicates')
        builder.make(
            conjunction_entity, 'Conjunction', conjunction, join='AND')
        all_conjunctions.append(conjunction_entity)

    if len(all_conjunctions) > 1:
      # The general case of what we actually model
      disjunction_entity = snapshot.new_entity(summary='OR expressions')
      builder.make(
          disjunction_entity, 'Disjunction', all_conjunctions, join='OR')
    elif len(all_conjunctions) == 1:
      # A special case to optimize the report to remove the disjunction
      # since there is only one component anyay.
      disjunction_entity = all_conjunctions[0]
    else:
      disjunction_entity = None

    builder.make_control(entity, 'Verifiers', disjunction_entity)

  def __init__(self, title, **kwargs):
    """Construct instance.

    Args:
      title: The name of the verifier for reporting purposes only.
      dnf_verifiers: A list of lists of jc.ObservationVerifier where the outer
          list are OR'd together and the inner lists are AND'd together
          (i.e. disjunctive normal form).
    """
    self.__title = title
    self.__dnf_verifiers = kwargs.pop('dnf_verifiers', None) or []
    super(ObservationVerifier, self).__init__(**kwargs)

  def __eq__(self, verifier):
    return (self.__class__ == verifier.__class__
            and self.__title == verifier.title
            and self.__dnf_verifiers == verifier.dnf_verifiers)

  def __str__(self):
    return 'ObservationVerifier {0!r}'.format(self.__dnf_verifiers)

  def __call__(self, context, observation):
    """Verify the observation.

    Args:
      observation: The observation to verify.
      context: The execution context containing additional runtime data
         accumulated from the operation and test.

    Returns:
      ObservationVerifyResult containing the verification results.
    """
    builder = ObservationVerifyResultBuilder(observation)
    valid = False

    if not self.__dnf_verifiers:
      logging.getLogger(__name__).warn(
          'No verifiers were set, so "%s" will fail by default.', self.title)

    # Outer terms are or'd together.
    for term in self.__dnf_verifiers:
       # pylint: disable=bad-indentation
       term_valid = True
       # Inner terms are and'd together.
       for v in term:
          result = v(context, observation)
          builder.add_observation_verify_result(result)
          if not result:
            term_valid = False
            break
       if term_valid:
         valid = True
         break

    return builder.build(valid)


class _VerifierBuilderWrapper(object):
  def __init__(self, verifier):
    self.__verifier = verifier

  def build(self):
    return self.__verifier


class ObservationVerifierBuilder(JsonSnapshotableEntity):
  @property
  def title(self):
    return self.__title

  def __eq__(self, builder):
    # pylint: disable=protected-access
    return (self.__class__ == builder.__class__
            and self.__title == builder.title
            and self.__dnf_verifier_builders
            == builder.__adnf_verifier_builders
            and self.__current_builder_conjunction
            == builder.__current_builder_conjunction)

  def __init__(self, title):
    self.__title = title

    # This is a list of lists acting as a disjunction.
    # Each embedded list acts as a conjunction.
    self.__dnf_verifier_builders = []

    # This is the conjunction we're currently building.
    # It is not yet in the _dnf_verifier_builders.
    # If None then we'll add a new one when needed.
    self.__current_builder_conjunction = None

    # This is the term we're currently building.
    self.__current_builder = None

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    entity.add_metadata('_title', self.__title)
    snapshot.edge_builder.make(entity, 'Title', self.__title)
    snapshot.edge_builder.make(
        entity, 'Verifiers', self.__dnf_verifier_builders)
    super(ObservationVerifierBuilder, self).export_to_json_snapshot(
        snapshot, entity)

  def append_verifier(self, verifier, new_term=False):
    self.append_verifier_builder(
        _VerifierBuilderWrapper(verifier), new_term=new_term)

  def append_verifier_builder(self, builder, new_term=False):
    if new_term and self.__current_builder_conjunction:
      self.__dnf_verifier_builders.append(self.__current_builder_conjunction)
      self.__current_builder_conjunction = None

    if not self.__current_builder_conjunction:
      self.__current_builder_conjunction = [builder]
    else:
      self.__current_builder_conjunction.append(builder)

  def build(self):
    if self.__current_builder_conjunction:
      self.__dnf_verifier_builders.append(self.__current_builder_conjunction)
      self.__current_builder_conjunction = None

    disjunction = []
    for conjunction in self.__dnf_verifier_builders:
      verifiers = []
      for builder in conjunction:
        verifiers.append(builder.build())
      disjunction.append(verifiers)

    return self._do_build_generate(disjunction)

  def _do_build_generate(self, dnf_verifiers):
    return ObservationVerifier(title=self.__title, dnf_verifiers=dnf_verifiers)
