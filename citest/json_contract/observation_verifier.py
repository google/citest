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

from ..base.scribe import Scribable
from . import predicate


class ObservationVerifyResultBuilder(object):
  @property
  def validated_object_set(self):
    return self._valid_obj_set

  def __init__(self, observation):
    self._observation = observation
    self._failed_constraints = []

    # _valid_obj_map is a tuple (object, [list of valid PredicateResult on it])
    # as different constraints look at the objects in the observation, they
    # build up this map with the results to get all the reasons why a
    # particular observed object is considered good because the top-level
    # constraints form a disjunction.
    self._valid_obj_map = []

    # The _valid_obj_set is a set of objects meeting constriants that verify
    # them. All we need is one reason to think something is good.
    self._valid_obj_set = []  # Cannot be a set because it has unhashable things.
    self._good_results = []
    self._bad_results = []
    self._all_results = []

  def _add_valid_object_constraint(self, entry):
    obj = entry.obj
    result = entry.result
    for e in self._valid_obj_map:
      if e[0] == obj:
        if not obj in self._valid_obj_set:
          self._valid_obj_set.append(obj)
        e[1].append(result)
        return
    self._valid_obj_map.append((obj, [result]))

  def add_map_result(self, map_result):
    good_results = map_result.good_object_result_mappings
    self._good_results.extend(good_results)
    bad_results = map_result.bad_object_result_mappings
    self._bad_results.extend(bad_results)
    self._all_results.extend(map_result.results)

    if not good_results:
      self.add_failed_constraint_map_result(map_result)
      return
    for entry in good_results:
      self._add_valid_object_constraint(entry)

  def add_failed_constraint_map_result(self, map_result):
    self._failed_constraints.append(map_result.pred)

  def add_observation_verify_result(self, result):
    if self._observation != result._observation:
      raise ValueError("Observations differ.")

    self._all_results.extend(result.all_results)
    self._good_results.extend(result.good_results)
    self._bad_results.extend(result.bad_results)
    self._failed_constraints.extend(result._failed_constraints)

  def build(self, valid):
    return ObservationVerifyResult(
      valid=valid, observation=self._observation,
      all_results=self._all_results,
      good_results=self._good_results,
      bad_results=self._bad_results,
      failed_constraints=self._failed_constraints)


class ObservationVerifyResult(predicate.PredicateResult):
  """Tracks details from verifying a contract.

  Attributes:
    observation: observer.Observation for the observer providing the objects.
    all_results: All the constraints on all the objects
    good_results:list of (obj, CompositeResult)
    bad_results: list of (obj, CompositeResult)
    failed_constraint: list of (constraint, CompositeResult)
        with object failures for constraints that had no objects
    enumerated_summary_message: Variation of summary_messages but
        provides a bulleted list (one per line with indent).
  """
  @property
  def observation(self):
    return self._observation

  @property
  def all_results(self):
    return self._all_results

  @property
  def good_results(self):
    return self._good_results

  @property
  def bad_results(self):
    return self._bad_results

  @property
  def failed_constraints(self):
    return self._failed_constraints

  @property
  def enumerated_summary_message(self):
    results = self._good_results if self.valid else self._bad_results
    if not results:
      return ''

    return '  * {0}'.format(
        '\n  * '.join([str(elem) for elem in results]))

  def __init__(self, valid, observation,
               all_results, good_results, bad_results, failed_constraints,
               comment=None):
    super(ObservationVerifyResult, self).__init__(valid, comment=comment)

    self._observation = observation
    self._all_results = all_results
    self._good_results = good_results
    self._bad_results = bad_results
    self._failed_constraints = failed_constraints

  def _make_scribe_parts(self, scribe):
    parts = [
        scribe.part_builder.build_input_part('Observation', self._observation),
        scribe.part_builder.build_nested_part(
            'Failed Constraints', self._failed_constraints),
        scribe.part_builder.build_output_part(
            'All Results', self._all_results),
        scribe.build_nested_part('Good Results', self._good_results),
        scribe.build_nested_part('Bad Results', self._bad_results)]

    inherited = super(ObservationVerifyResult, self)._make_scribe_parts(scribe)
    return parts + inherited

  def __str__(self):
    return ('observation=<{0}>'
            '  good_results=<{1}>'
            '  bad_results=<{2}>'.format(
        self._observation,
        ','.join([str(e.result) for e in self._good_results]),
        ','.join([str(e.result) for e in self._bad_results])))

  def __eq__(self, state):
    return (super(ObservationVerifyResult, self).__eq__(state)
            and self._observation == state._observation
            and self._all_results == state._all_results
            and self._good_results == state._good_results
            and self._bad_results == state._bad_results
            and self._failed_constraints == state._failed_constraints)


class ObservationVerifier(predicate.ValuePredicate):
  @property
  def dnf_verifiers(self):
    return self._dnf_verifiers

  @property
  def title(self):
    return self._title

  def _make_scribe_parts(self, scribe):
    disjunction = self._dnf_verifiers
    disjunction_segments = []
    scribe.push_level()
    for conjunction in disjunction:
      segments = []
      for elem in conjunction:
        segments.append(scribe.render(elem))
      disjunction_segments.append(
          '\n{and_indent}AND '.format(and_indent=scribe.line_indent).join(
          segments))
    if not disjunction_segments:
      disjunction_segments = ['<no verifiers>']

    verifiers = '\n{or_indent}OR '.format(or_indent=scribe.line_indent).join(
        disjunction_segments)
    scribe.pop_level()

    parts = [
        scribe.build_part('Title', self._title),
        scribe.part_builder.build_control_part(
            'Verifiers', verifiers, renderer=scribe.identity_renderer)]
    return parts

  def __init__(self, title, dnf_verifiers=None):
    """Construct instance.

    Args:
      title: The name of the verifier for reporting purposes only.
      dnf_verifiers: A list of lists of jc.ObservationVerifier where the outer
          list are OR'd together and the inner lists are AND'd together
          (i.e. disjunctive normal form).
    """
    self._title = title
    self._dnf_verifiers = dnf_verifiers or []

  def __eq__(self, verifier):
    return (self.__class__ == verifier.__class__
            and self._title == verifier._title
            and self._dnf_verifiers == verifier._dnf_verifiers)

  def __str__(self):
    return 'ObservationVerifier {0!r}'.format(self._dnf_verifiers)

  def __call__(self, observation):
    """Verify the observation.

    Args:
      observation: The observation to verify.

    Returns:
      ObservationVerifyResult containing the verification results.
    """
    builder = ObservationVerifyResultBuilder(observation)
    valid = False

    # Outer terms are or'd together.
    for term in self._dnf_verifiers:
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
    self._verifier = verifier

  def build(self):
    return self._verifier


class ObservationVerifierBuilder(Scribable):
  @property
  def title(self):
    return self._title

  def __eq__(self, builder):
    return (self.__class__ == builder.__class__
            and self._title == builder._title
            and self._dnf_verifier_builders == builder._dnf_verifier_builders
            and self._current_builder_conjunction
                == builder._current_builder_conjunction)

  def __init__(self, title):
    self._title = title

    # This is a list of lists acting as a disjunction.
    # Each embedded list acts as a conjunction.
    self._dnf_verifier_builders = []

    # This is the conjunction we're currently building.
    # It is not yet in the _dnf_verifier_builders.
    # If None then we'll add a new one when needed.
    self._current_builder_conjunction = None

    # This is the term we're currently building.
    self._current_builder = None

  def _make_scribe_parts(self, scribe):
    parts = [
      scribe.build_part('Title', self._title),
      scribe.build_part('Verifiers', self._dnf_verifier_builders)]
    inherited = super(ObservationVerifierBuilder, self)._make_scribe_parts(
      scribe)
    return parts + inherited

  def append_verifier(self, verifier, new_term=False):
    self.append_verifier_builder(
      _VerifierBuilderWrapper(verifier), new_term=new_term)

  def append_verifier_builder(self, builder, new_term=False):
    if new_term and self._current_builder_conjunction:
      self._dnf_verifier_builders.append(self._current_builder_conjunction)
      self._current_builder_conjunction = None

    if not self._current_builder_conjunction:
      self._current_builder_conjunction = [builder]
    else:
      self._current_builder_conjunction.append(builder)

  def build(self):
    if self._current_builder_conjunction:
      self._dnf_verifier_builders.append(self._current_builder_conjunction)
      self._current_builder_conjunction = None

    disjunction = []
    for conjunction in self._dnf_verifier_builders:
      verifiers = []
      for builder in conjunction:
        verifiers.append(builder.build())
      disjunction.append(verifiers)

    return self._do_build_generate(disjunction)

  def _do_build_generate(self, dnf_verifiers):
    return ObservationVerifier(title=self._title, dnf_verifiers=dnf_verifiers)
