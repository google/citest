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

"""Implementation of PathPredicateResult and PathPredicateResultBuilder."""


import collections
from ..base import JsonSnapshotableEntity
from . import predicate


class PathPredicateResultCandidate(
    collections.namedtuple('PathPredicateResultCandidate',
                           ['path_value', 'result']),
    JsonSnapshotableEntity):
  """Holds a value matching the desired path with its filtering result."""
  # pylint: disable=too-few-public-methods

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_output(
        entity, 'Path Value', self.path_value)
    snapshot.edge_builder.make_output(
        entity, 'Justification', self.result)


class PathPredicateResultBuilder(object):
  """Builder for creating PathPredicateResult instances."""

  @property
  def source(self):
    """The source the bound path predicate was applied to."""
    return self.__source

  @property
  def pred(self):
    """The PathPredicate that generated the result."""
    return self.__pred

  def __init__(self, source, pred):
    """Constructor.

    Args:
      source: [obj] The JSON object used to collect the values.
      pred: [ValuePredicate] The predicate used to gather the results.
    """
    self.__source = source
    self.__pred = pred
    self.__path_values = []
    self.__path_failures = []
    self.__invalid_candidates = []
    self.__valid_candidates = []

  def add_all_path_failures(self, failures):
    """Adds to the list of failed results.

    Args:
      failures: [list of PredicateResult] Explains reason paths were
          omitted before we reached the final candidates..
    """
    self.__path_failures.extend(failures)
    return self

  def add_path_failure(self, failure):
    """Adds to the list of pruned paths.

    Args:
      failure: [PredicateResult] Explains the reason a path was pruned.
    """
    self.__path_failures.append(failure)
    return self

  def add_result_candidate(self, path_value, final_result):
    """Adds to the list of collected values.

    Args:
      path_value: [PathValue] A value that meets the bound path criteria.
      final_result: [ValueResult] The result from the bound predicate filter
          that justifies whether the value is valid (meets the filter criteria)
          or not.
    """
    candidate_result = PathPredicateResultCandidate(path_value, final_result)
    if final_result:
      self.__valid_candidates.append(candidate_result)
      self.__path_values.append(path_value)
    else:
      self.__invalid_candidates.append(candidate_result)
    return self

  def build(self, valid=None):
    """Construct the result.

    Returns:
      PathPredicateResult
    """
    if valid is None:
      valid = len(self.__path_values) > 0
    return PathPredicateResult(
        valid=valid, pred=self.__pred, source=self.__source,
        path_failures=self.__path_failures,
        valid_candidates=self.__valid_candidates,
        invalid_candidates=self.__invalid_candidates)


class HasPathPredicateResult(object):
  """This is a hack in lieu of a more meaningful interface.

  The purpose of this is to allow observation validators to
  be able to access the actual observed objects as well as how
  they complied with constraints. This is needed for certain types
  of constraints. Rather than coming up with the right interface at
  this time, we'll just mooch off the PathPredicateResult which is
  the basis of extracting values from observations and of the
  CardinalityPredicate for counting instances.
  """
  # pylint: disable=too-few-public-methods

  @property
  def path_predicate_result(self):
    """A PathPredicateResult instance providing the applicable object values."""
    raise NotImplementedError(self.__class__.__name__)


class PathPredicateResult(predicate.PredicateResult, HasPathPredicateResult):
  """Class containing results of collecting values at a path.

  This contains both the values that were collected, as well as the
  values encountered that could not be collected. The "bad" values may
  not have had a complete path or may have failed a filtering predicate.
  Either way, we remember them here for the sake of reporting to show
  why these encountered values were not among those "good" values collected.

  Future operations on the collected values, typically imply only the "good"
  values.
  """

  @property
  def path_predicate_result(self):
    """Implements HasPathPredicateResult interface."""
    return self

  @property
  def pred(self):
    """The predicate used to filter values, if any."""
    return self.__pred

  @property
  def path_values(self):
    """The matching PathValue instances that were found."""
    return self.__path_values

  @property
  def source(self):
    """Returns the source collected from."""
    return self.__source

  @property
  def values(self):
    """A list of the value components of the matching PathValue list."""
    return [value.value for value in self.__path_values]

  @property
  def path_failures(self):
    """A list of PredicateResult for each path that did not lead to a value.

    This list contains only the point of first failure for each potential
    path node to explain why it was pruned.
    """
    return self.__path_failures

  @property
  def valid_candidates(self):
    """List of PredicateResultCandidate justifying each good PathValue."""
    return self.__valid_candidates

  @property
  def invalid_candidates(self):
    """List of PredicateResultCandidate justifying each failed path.

    This does not include the pruned paths, only the valid paths that
    failed the bound predicate to filter values.
    """
    return self.__invalid_candidates

  def __init__(self, valid, pred, source, path_failures=None,
               valid_candidates=None, invalid_candidates=None):
    """Constructor.

    Args:
      valid: [bool] Whether or not the result is valid.
      pred: [ValuePredicate] The filtering predicate might be None.
      source: [obj] The root JSON object that was traversed.
      path_failures: [list of PredicateResult] The pruned paths.
      valid_candidates: [list of PathPredicateResultCandidate]
      invalid_candidates: [list of PathPredicateResultCandidate]
    """
    # pylint: disable=too-many-arguments
    super(PathPredicateResult, self).__init__(valid)
    self.__pred = pred
    self.__source = source
    self.__path_values = [candidate.path_value
                          for candidate in valid_candidates]
    self.__path_failures = path_failures or []
    self.__invalid_candidates = invalid_candidates or []
    self.__valid_candidates = valid_candidates or []

  def __eq__(self, result):
    """Specializes interface."""
    return (super(PathPredicateResult, self).__eq__(result)
            and self.__pred == result.pred
            and self.__source == result.source
            and self.__valid_candidates == result.valid_candidates
            and self.__invalid_candidates == result.invalid_candidates
            and self.__path_values == result.path_values
            and self.__path_failures == result.path_failures)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self.__pred)
    # Separate out just the path values from the full justification (below)
    # to make it easy to get at the list of values found, which is often
    # of particular interest.
    snapshot.edge_builder.make_output(
        entity, 'Path Values', self.__path_values)

    if self.__path_failures:
      snapshot.edge_builder.make_output(
          entity, 'Pruned Paths', self.__path_failures)
    if self.__invalid_candidates:
      snapshot.edge_builder.make_output(
          entity, 'Rejected Values', self.__invalid_candidates)

    # The full justification for the values found in the Path Value list.
    # This is the full PredicateResult that validated the value, so
    # contains another copy of each value (adding full traceability).
    if self.__valid_candidates:
      snapshot.edge_builder.make_output(
          entity, 'Value Justifications', self.__valid_candidates)

  def __str__(self):
    """Specializes interface."""
    return '{0} #valid={1} #invalid={2} #pruned={3}'.format(
        self.__class__.__name__,
        len(self.valid_candidates), len(self.invalid_candidates),
        len(self.path_failures))

  def __repr__(self):
    """Specializes interface."""
    return ('{0} pred={1} path_values={2} pruned={3} invalid={4} valid={5}'
            .format(self.__class__.__name__, self.pred, self.path_values,
                    self.path_failures,
                    self.invalid_candidates, self.valid_candidates))
