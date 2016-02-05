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

from ..base import JsonSnapshotable
from . import predicate


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
    self.__all_results = []

  def __add_valid_object_constraint(self, entry):
    obj = entry.obj
    result = entry.result
    for e in self.__valid_obj_map:
      if e[0] == obj:
        e[1].append(result)
        return

    self.__valid_obj_set.append(obj)
    self.__valid_obj_map.append((obj, [result]))

  def add_map_result(self, map_result):
    good_results = map_result.good_object_result_mappings
    self.__good_results.extend(good_results)
    bad_results = map_result.bad_object_result_mappings
    self.__bad_results.extend(bad_results)
    self.__all_results.extend(map_result.results)

    if not good_results:
      self.add_failed_constraint_map_result(map_result)
      return
    for entry in good_results:
      self.__add_valid_object_constraint(entry)

  def add_failed_constraint_map_result(self, map_result):
    self.__failed_constraints.append(map_result.pred)

  def add_observation_verify_result(self, result):
    if self.__observation != result.observation:
      raise ValueError("Observations differ.")

    self.__all_results.extend(result.all_results)
    self.__good_results.extend(result.good_results)
    self.__bad_results.extend(result.bad_results)
    self.__failed_constraints.extend(result.failed_constraints)

  def build(self, valid):
    return ObservationVerifyResult(
        valid=valid, observation=self.__observation,
        all_results=self.__all_results,
        good_results=self.__good_results,
        bad_results=self.__bad_results,
        failed_constraints=self.__failed_constraints)


class ObservationVerifyResult(predicate.PredicateResult):
  """Tracks details from verifying a contract.
  """
  @property
  def observation(self):
    """observer.Observation for the observer providing the objects."""
    return self.__observation

  @property
  def all_results(self):
    """All the constraints on all the objects."""
    return self.__all_results

  @property
  def good_results(self):
    """List of (obj, CompositeResult)."""
    return self.__good_results

  @property
  def bad_results(self):
    """List of (obj, CompositeResult)."""
    return self.__bad_results

  @property
  def failed_constraints(self):
    """List of (constraint, CompositeResult) for constraints with no objects.
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
        '\n  * '.join([str(elem) for elem in results]))

  def __init__(self, valid, observation,
               all_results, good_results, bad_results, failed_constraints,
               comment=None):
    super(ObservationVerifyResult, self).__init__(valid, comment=comment)

    self.__observation = observation
    self.__all_results = all_results
    self.__good_results = good_results
    self.__bad_results = bad_results
    self.__failed_constraints = failed_constraints

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    super(ObservationVerifyResult, self).export_to_json_snapshot(
        snapshot, entity)
    builder = snapshot.edge_builder
    builder.make_input(entity, 'Observation', self.__observation)
    builder.make(entity, 'Failed Constraints', self.__failed_constraints)
    builder.make_output(entity, 'All results', self.__all_results)
    edge = builder.make(entity, 'Good Results', self.__good_results)
    if self.__good_results:
      edge.add_metadata('relation', 'VALID')
    edge = builder.make(entity, 'Bad Results', self.__bad_results)
    if self.__bad_results:
      edge.add_metadata('relation', 'INVALID')

  def __str__(self):
    return ('observation=<{0}>'
            '  good_results=<{1}>'
            '  bad_results=<{2}>'.format(
                self.__observation,
                ','.join([str(e.result) for e in self.__good_results]),
                ','.join([str(e.result) for e in self.__bad_results])))

  def __eq__(self, state):
    return (super(ObservationVerifyResult, self).__eq__(state)
            and self.__observation == state.observation
            and self.__all_results == state.all_results
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
    """Implements JsonSnapshotable interface."""
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
        all_conjunctions.append(snapshot.make_entity_for_data(conjunction[0]))
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

  def __init__(self, title, dnf_verifiers=None):
    """Construct instance.

    Args:
      title: The name of the verifier for reporting purposes only.
      dnf_verifiers: A list of lists of jc.ObservationVerifier where the outer
          list are OR'd together and the inner lists are AND'd together
          (i.e. disjunctive normal form).
    """
    self.__title = title
    self.__dnf_verifiers = dnf_verifiers or []

  def __eq__(self, verifier):
    return (self.__class__ == verifier.__class__
            and self.__title == verifier.title
            and self.__dnf_verifiers == verifier.dnf_verifiers)

  def __str__(self):
    return 'ObservationVerifier {0!r}'.format(self.__dnf_verifiers)

  def __call__(self, observation):
    """Verify the observation.

    Args:
      observation: The observation to verify.

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
          result = v(observation)
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


class ObservationVerifierBuilder(JsonSnapshotable):
  @property
  def title(self):
    return self.__title

  def __eq__(self, builder):
    return (self.__class__ == builder.__class__
            and self.__title == builder.title
            and self.__dnf_verifier_builders == builder.__adnf_verifier_builders
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
    """Implements JsonSnapshotable interface."""
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
