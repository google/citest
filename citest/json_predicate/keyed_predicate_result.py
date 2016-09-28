# Copyright 2016 Google Inc. All Rights Reserved.
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


class KeyedPredicateResult(PredicateResult, CloneableWithNewSource):
  """Aggregates a collection of predicate results into a single response.

  Each of the individual results is accessible by a string key value.

  This result is used by predicates that are composed out of multiple parts,
  some or all of which wish to contribute to the final result. For example
  a named collection of predicates where the final result wishes to contain
  the intermediate reuslts that it had considered.

  The results are keyed with a string value. The key used depends on the
  semantics of the predicate returning it, which may or may not be arbitrary.

  Attributes:
    pred: The ValuePredicate doing the aggregation.
    results: The dictionary of PredicateResponse instances being aggregated.
  """

  @property
  def pred(self):
    """The predicate used to collect the composite results."""
    return self.__pred

  @property
  def results(self):
    """The map of PredicateResult instances."""
    return self.__results

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder
    summary = builder.object_count_to_summary(
        self.__results, subject='composite result by key')
    builder.make_mechanism(entity, 'Predicate', self.__pred)
    builder.make(entity, '#', len(self.__results))

    result_entity = snapshot.new_entity(summary=summary)
    for key, result in self.__results.items():
      builder.make(result_entity, '[{0}]'.format(key), result,
                   relation=builder.determine_valid_relation(result),
                   summary=result.summary)
    builder.make(entity, 'Results', result_entity,
                 relation=builder.determine_valid_relation(self))
    super(KeyedPredicateResult, self).export_to_json_snapshot(
        snapshot, entity)

  def __str__(self):
    return '{0}'.format(self.__results)

  def __init__(self, valid, pred, results, **kwargs):
    super(KeyedPredicateResult, self).__init__(valid, **kwargs)
    self.__pred = pred
    self.__results = results

  def __eq__(self, result):
    return (super(KeyedPredicateResult, self).__eq__(result)
            and self.__pred == result.pred
            and self.__results == result.results)

  def clone_with_source(self, source, base_target_path, base_value_path):
    """Implements CloneableWithNewSource interface.

    A composite result has no context, but its components may.
    """
    results = {}
    for key, orig in self.__results.items():
      if isinstance(orig, CloneableWithNewSource):
        results[key] = orig.clone_with_source(
            source=source,
            base_target_path=base_target_path,
            base_value_path=base_value_path)
      else:
        results[key] = orig

    return self.__class__(self.valid, self.__pred, results,
                          comment=self.comment, cause=self.cause)


class KeyedPredicateResultBuilder(object):
  """Helper class for building a keyed result."""

  def __init__(self, pred):
    self.__pred = pred
    self.cause = None
    self.comment = None
    self.__results = {}

  def add_result(self, key, result):
    """Adds a result to the list of results captured.

    Args:
      key: [String] The key to add the result under should be unique.
      result: [PredicateResult] The result to add.
    """
    if key in self.__results:
      raise ValueError('{0} already exists.'.format(key))
    self.__results[key] = result
    return self

  def update_results(self, results):
    """Adds a dictionary of results to the composite list of results captured.

    Args:
      results: [dictionary of PredicateResult] The results to add.
    """
    self.__results.update(results)
    return self

  def build(self, valid):
    """Construct the specified KeyedPredicateResult instance.

    Args:
      valid: [bool]  Whether the result is considered successful or not.
    """
    return KeyedPredicateResult(
        valid, self.__pred, self.__results,
        comment=self.comment, cause=self.cause)
