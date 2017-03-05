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

"""Aggregates a list of predicate results into a single response."""

from .predicate import (
    CloneableWithNewSource,
    PredicateResult)

class SequencedPredicateResult(PredicateResult, CloneableWithNewSource):
  """Aggregates a list of predicate results into a single response.

  Each of the individual results is accessible by a scalar index value.

  This result is used by predicates that are composed out of multiple parts,
  some or all of which wish to contribute to the final result. For example
  a disjunction where the final result wishes to contain the intermediate
  results that it had OR'd together.

  The results are sequenced linearly. The order of results depends on the
  semantics of the predicate returning it, which may or may not be arbitrary.

  Attributes:
    pred: The ValuePredicate doing the aggregation.
    results: The list of PredicateResponse instances being aggregated.
  """

  @property
  def pred(self):
    """The predicate used to collect the composite results."""
    return self.__pred

  @property
  def results(self):
    """The list of PredicateResult instances."""
    return self.__results

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder
    summary = builder.object_count_to_summary(
        self.__results, subject='sequenced composite result')
    builder.make_mechanism(entity, 'Predicate', self.__pred)
    builder.make(entity, '#', len(self.__results))

    result_entity = snapshot.new_entity(summary=summary)
    for index, result in enumerate(self.__results):
      builder.make(result_entity, '[{0}]'.format(index), result,
                   relation=builder.determine_valid_relation(result),
                   summary=result.summary)
    if self.__keep_results_attribute_in_snapshot:
      builder.make(entity, 'Results', result_entity,
                   relation=builder.determine_valid_relation(self))
    super(SequencedPredicateResult, self).export_to_json_snapshot(
        snapshot, entity)

  def __str__(self):
    return '{0}'.format(self.__results)

  def __init__(self, valid, pred, results, **kwargs):
    self.__keep_results_attribute_in_snapshot = kwargs.pop(
        'keep_results_attribute_in_snapshot', True)
    super(SequencedPredicateResult, self).__init__(valid, **kwargs)
    self.__pred = pred
    self.__results = results

  def __eq__(self, result):
    return (super(SequencedPredicateResult, self).__eq__(result)
            and self.__pred == result.pred
            and self.__results == result.results)

  def clone_with_source(self, source, base_target_path, base_value_path):
    """Implements CloneableWithNewSource interface.

    A composite result has no context, but its components may.
    """
    results = []
    for orig in self.__results:
      if isinstance(orig, CloneableWithNewSource):
        results.append(
            orig.clone_with_source(source=source,
                                   base_target_path=base_target_path,
                                   base_value_path=base_value_path))
      else:
        results.append(orig)

    return self.__class__(self.valid, self.__pred, results,
                          comment=self.comment, cause=self.cause)


class SequencedPredicateResultBuilder(object):
  """Helper class for building a sequenced composite result."""

  def __init__(self, pred):
    self.__pred = pred
    self.cause = None
    self.comment = None
    self.__results = []

  def append_result(self, result):
    """Adds a result to the list of results captured.

    Args:
      result: [PredicateResult] The result to add.
    """
    self.__results.append(result)
    return self

  def extend_results(self, results):
    """Adds a list of results to the list of results captured.

    Args:
      results: [list of PredicateResult] The results to add.
    """
    self.__results.extend(results)
    return self

  def build(self, valid):
    """Construct the specified SequencedPredicateResult instance.

    Args:
      valid: [bool]  Whether the result is considered successful or not.
    """
    return SequencedPredicateResult(
        valid, self.__pred, self.__results,
        comment=self.comment, cause=self.cause)
