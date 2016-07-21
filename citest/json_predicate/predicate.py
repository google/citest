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

"""Implements ValuePredicate that determines when a given value is 'valid'."""


from ..base import JsonSnapshotable


class ValuePredicate(JsonSnapshotable):
  """Base class denoting a predicate that determines if a JSON value is ok.

   This class must be specialized with a __call__ method that takes a single
   value object and returns None if the value is acceptable, or a JsonError
   explaining why it is not.

   The intent of this class is to check if a JSON object contains fields
   with particular values, ranges or other properties.
  """
  # pylint: disable=too-few-public-methods

  def __call__(self, value):
    """Apply this predicate against the provided value.

    Args:
      value: The value to consider.

    Returns:
      PredicateResult with the value if valid, or error if not valid.
    """
    raise NotImplementedError(
        '__call__() needs to be specialized for {0}'.format(
            self.__class__.__name__))

  def __repr__(self):
    """Specializes interface."""
    return str(self)

  def __ne__(self, pred):
    return not self.__eq__(pred)


class PredicateResult(JsonSnapshotable):
  """Base class for predicate results.

  Attributes:
    cause: Typically for errors, if this is non-empty then it indicates
      some upstream reason why this predicate failed that is usually
      out of band (e.g. an exception or preprocessing failure).
    comment: An error message string for reporting purposes only.
    valid: A boolean indicating whether the result is considerd valid or not.
    """

  @property
  def summary(self):
    """An abstract summary of the result for reporting purposes."""
    valid_str = 'GOOD' if self.__valid else 'BAD'
    message = self.comment if self.comment else self.__class__.__name__
    return '{message} ({valid})'.format(message=message, valid=valid_str)

  @property
  def comment(self):
    """Optional informal commentary added to the result."""
    return self.__comment

  @property
  def cause(self):
    """Optional cause triggering the result, intended for indirect errors."""
    return self.__cause

  @property
  def valid(self):
    """Whether or not the result should be considered 'successful'."""
    return self.__valid

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    verified_relation = builder.determine_valid_relation(self.__valid)
    builder.make(entity, 'Valid', self.__valid, relation=verified_relation)
    if self.__comment:
      builder.make(entity, 'Comment', self.__comment)
    if self.__cause:
      builder.make(entity, 'Cause', self.__cause)

    # Set a default relation so that this can be picked up when it appears
    # as a list element.
    entity.add_metadata('_default_relation', verified_relation)

  def __init__(self, valid, comment="", cause=None):
    """Constructor

    Args:
      valid: [bool] Whether the result is considered successful or not.
      comment: [string] Optional informal commentary for reporting purposes.
      cause: [Error or PredicateResult] Optional indirect cause [for errors].
    """
    self.__valid = valid
    self.__comment = comment
    self.__cause = cause

  def __repr__(self):
    return str(self)

  def __str__(self):
    return (self.__comment
            or '{0} is {1}'.format(self.__class__.__name__,
                                   'OK' if self.__valid else 'FAILURE'))

  def __nonzero__(self):
    return self.__valid

  def __eq__(self, result):
    if (self.__class__ != result.__class__
        or self.__valid != result.valid
        or self.__comment != result.comment):
      return False

    # If cause was an exception then just compare classes.
    # Otherwise compare causes.
    # We assume cause is None, and Exception, or another PredicateResult.
    # Exceptions do not typically support value equality.
    if self.__cause != result.cause:
      return (isinstance(self.__cause, Exception)
              and self.__cause.__class__ == result.cause.__class__)
    return self.__cause == result.cause

  def __ne__(self, result):
    return not self.__eq__(result)


class CloneableWithContext(object):
  """Indicates that a PredicateResult can be cloned with a new context.

  Some PredicateResult type contain context information about where the
  internal values came from (e.g. the path to the value). When these are
  constructed, they contain the local context information. Sometimes there
  are higher level predicates that are using these, then propagating the
  results back. These higher level predicates contain additional scope
  that should be "injected" into the lower level result details. Since
  results are immutable, we will clone them. This interface allows
  results with context to clone a copy of themself and inject the additional
  context into the newly cloned instance.
  """
  # pylint: disable=too-few-public-methods

  def clone_in_context(self, source, base_target_path, base_value_path):
    """Clone the instance with a new context.

    Args:
      source: [obj] JSON object for the new context.
      base_target_path: [string] The additional context path relative to
         |source| to get at the desired result context.
      base_value_path: [string] The additional context path relative to
         |source| to get at the actual values found. This is similar to
         the base_target_path but may have further refinements for path
         elements (e.g. array indecies taken).
    """
    raise NotImplementedError()


class CompositePredicateResult(PredicateResult, CloneableWithContext):
  """Aggregates a collection of predicate results into a single response.

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
        self.__results, subject='composite result')
    builder.make_mechanism(entity, 'Predicate', self.__pred)
    builder.make(entity, '#', len(self.__results))

    result_entity = snapshot.new_entity(summary=summary)
    for index, result in enumerate(self.__results):
      builder.make(result_entity, '[{0}]'.format(index), result,
                   relation=builder.determine_valid_relation(result),
                   summary=result.summary)
    builder.make(entity, 'Results', result_entity,
                 relation=builder.determine_valid_relation(self))
    super(CompositePredicateResult, self).export_to_json_snapshot(
        snapshot, entity)

  def __str__(self):
    return '{0}'.format(self.__results)

  def __init__(self, valid, pred, results, comment=None, cause=None):
    super(CompositePredicateResult, self).__init__(
        valid, comment=comment, cause=cause)
    self.__pred = pred
    self.__results = results

  def __eq__(self, result):
    return (super(CompositePredicateResult, self).__eq__(result)
            and self.__pred == result.pred
            and self.__results == result.results)

  def clone_in_context(self, source, base_target_path, base_value_path):
    """Implements CloneableWithContext interface.

    A composite result has no context, but its components may.
    """
    results = []
    for orig in self.__results:
      if isinstance(orig, CloneableWithContext):
        results.append(
            orig.clone_in_context(source=source,
                                  base_target_path=base_target_path,
                                  base_value_path=base_value_path))
      else:
        results.append(orig)

    return self.__class__(self.valid, self.__pred, results,
                          comment=self.comment, cause=self.cause)


class CompositePredicateResultBuilder(object):
  """Helper class for building a composite result."""

  def __init__(self, pred):
    self.__pred = pred
    self.cause = None
    self.comment = None
    self.__results = []

  def append_result(self, result):
    """Adds a result to the composite list of results captured.

    Args:
      result: [PredicateResult] The result to add.
    """
    self.__results.append(result)
    return self

  def extend_results(self, results):
    """Adds a list of results to the composite list of results captured.

    Args:
      results: [list of PredicateResult] The results to add.
    """
    self.__results.extend(results)
    return self

  def build(self, valid):
    """Construct the specified CompositePredicateResult instance.

    Args:
      valid: [bool]  Whether the result is considered successful or not.
    """
    return CompositePredicateResult(
        valid, self.__pred, self.__results, self.comment, self.cause)
