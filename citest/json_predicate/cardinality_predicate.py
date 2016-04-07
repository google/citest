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

"""A predicate that count the number of values that satisfy another predicate.
"""


from . import predicate
from . import path_predicate as pp
from .path_predicate_result import HasPathPredicateResult


class CardinalityResult(predicate.PredicateResult, HasPathPredicateResult):
  """Denotes a PredicateResult from a CardinalityPredicate.

  In practice, this is a base class that is further refined for specific
  types of events.

  Attributes:
    pred: The ValuePredicate genearting the result.
    found: A list of JSON objects the predicate was applied to.
        In practice these are the matched objects.
  """

  @property
  def path_predicate_result(self):
    """The result of mapping the underlying predicate over the source."""
    return self.__collect_values_result

  @property
  def pred(self):
    """Returns the cardinality predicate used to generate this result."""
    return self.cardinality_pred

  @property
  def path_pred(self):
    """The underlying path predicate used to collect values."""
    return self.__collect_values_result.pred

  @property
  def filter_pred(self):
    """The filter to the underlying path predicate."""
    return self.__collect_values_result.pred.pred

  @property
  def cardinality_pred(self):
    """The actual CardinalityPredicate used to generate this result."""
    return self.__cardinality_pred

  @property
  def count(self):
    """The number of elements that satisfied the predicate."""
    return len(self.__collect_values_result.path_values)

  @property
  def source(self):
    """The source value (collection) that we are mapping the predicateover."""
    return self.__collect_values_result.source

  def __init__(self, cardinality_pred, path_pred_result, valid=False):
    """Constructor.

    Args:
      cardinality_pred: [CardinalityPredicate] The predicate we used to
          generate this result.
      pred_result: [CollectValuesResult]. The result of applying the
          underlying PathPredicate bound to the |cardinality_pred|.
      valid: [bool] Whether or not the cardinality predicate was satisfied.
    """
    super(CardinalityResult, self).__init__(valid)
    self.__cardinality_pred = cardinality_pred
    self.__collect_values_result = path_pred_result

  def __repr__(self):
    return '{0} pred={1!r} result={2!r}'.format(
        self.__class__.__name__,
        self.__cardinality_pred, self.__collect_values_result)

  def __str__(self):
    return '{valid} count={count} of {min}...{max}'.format(
        valid=self.valid, count=self.count,
        min=self.__cardinality_pred.min, max=self.__cardinality_pred.max)

  def __eq__(self, event):
    return (self.__class__ == event.__class__
            and self.__cardinality_pred == event.cardinality_pred
            and self.__collect_values_result == event.path_predicate_result)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    count_relation = builder.determine_valid_relation(self)
    result_relation = builder.determine_valid_relation(
        self.__collect_values_result)
    builder.make(entity, 'Count', self.count, relation=count_relation)
    builder.make_mechanism(entity, 'Predicate', self.__cardinality_pred)
    builder.make_input(entity, 'Source',
                       self.__collect_values_result.source, format='json')
    builder.make(entity, 'Result',
                 self.__collect_values_result, relation=result_relation)


class ConfirmedCardinalityResult(CardinalityResult):
  """Denotes a CardinalityPredicate that was satisfied."""

  def __init__(self, cardinality_pred, path_pred_result, valid=False):
    """Constructor.

    Args:
      cardinality_pred: [CardinalityPredicate] The predicate we used to
          generate this result.
      pred_result: [CollectValuesResult]. The result of applying the
          underlying PathPredicate bound to the |cardinality_pred|.
      valid: [bool] Whether or not the cardinality predicate was satisfied.
    """
    super(ConfirmedCardinalityResult, self).__init__(
        cardinality_pred=cardinality_pred, path_pred_result=path_pred_result,
        valid=valid)

  def __str__(self):
    if not self.count:
      return 'Confirmed no {pred}.'.format(pred=self.path_pred)

    return 'Confirmed pred={pred} with count={count}'.format(
        pred=self.cardinality_pred, count=self.count)


class FailedCardinalityResult(CardinalityResult):
  """Denotes a CardinalityPredicate that was not satisfied.

  In practice, this is a base class used to detect failures.
  It is further specialized for the particular reason for failure.
  """
  pass


class UnexpectedValueCardinalityResult(FailedCardinalityResult):
  """Denotes a failure because a value existed where none were expected."""

  def __str__(self):
    return 'Found unexpected count={count} pred={pred}'.format(
        count=self.count, pred=self.cardinality_pred)


class MissingValueCardinalityResult(FailedCardinalityResult):
  """Denotes a failure because a value did not exist where one was expected."""

  def __init__(self, source, cardinality_pred, path_pred_result,
               valid=True):
    super(MissingValueCardinalityResult, self).__init__(
        valid=valid, cardinality_pred=cardinality_pred,
        path_pred_result=path_pred_result)
    self.__source = source

  def __str__(self):
    return 'Expected to find {pred}. No values found.'.format(
        pred=self.cardinality_pred)


class FailedCardinalityRangeResult(FailedCardinalityResult):
  """Denotes a failure because too few or too many values were found."""

  def __str__(self):
    # pred is a CardinalityPredicate
    return ('Found {count} {criteria}'
            ' but expected {min}..{max}'.format(
                count=self.count, criteria=self.path_pred,
                min=self.cardinality_pred.min, max=self.cardinality_pred.max))


class CardinalityPredicate(predicate.ValuePredicate,
                           pp.ProducesPathPredicateResult):
  """Validates a JSON object value based on how many things are found within.

  We implicitly wrap the predicate in a MapPredicate so that the results
  coming back have a structure that makes sense. But we dont bother passing
  the MapPredicate in because it is implicit. Instead we just pass in the
  predicate to be mapped.

  Attributes:
    pred: jc.ValuePredicate to apply is implictly wrapped in a MapPredicate.
    min: Minimum number of expected object matches we expect.
    max: Maximum number of expected object matches we allow. < 0 indicates any.
  """
  @property
  def path_pred(self):
    """The underlying predicate that we are mapping."""
    return self.__path_pred

  @property
  def filter_pred(self):
    """The filter, if any, for the underlying path predicate."""
    return self.__path_pred.pred

  @property
  def min(self):
    """The minimum desired cardinality, or None for no lower bound."""
    return self.__min

  @property
  def max(self):
    """The maximum desired cardinality, or None for no upper bound."""
    return self.__max

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self.path_pred)
    snapshot.edge_builder.make_control(entity, 'Min', self.__min)
    snapshot.edge_builder.make_control(entity, 'Max',
                                       'Any' if self.__max < 0 else self.__max)

  def __init__(self, pred, min=0, max=None):
    """Constructor.

    Args:
      pred: The jc.ValuePredicate to apply.
      min: The minimum number of path values we expect to find when applied.
      max: The maximum number of path values we expect to find when applied.
    """
    if not isinstance(pred, predicate.ValuePredicate):
      raise TypeError(
          'Got {0}, expected jc.ValuePredicate'.format(pred.__class__))

    self.__min = min
    self.__max = max
    if isinstance(pred, pp.PathPredicate):
      self.__path_pred = pred
    else:
      self.__path_pred = pp.PathPredicate('', pred=pred)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__min == pred.min
            and self.__max == pred.max
            and self.__path_pred == pred.path_pred)

  def __str__(self):
    return 'Cardinality({0}) {1}..{2}'.format(
        self.__path_pred, self.__min, self.__max)

  def __call__(self, obj):
    """Attempt to match object.

    Args:
      obj: JSON object to match.

    Returns:
      PredicateResponse
    """
    collected_result = self.__path_pred(obj)
    count = len(collected_result.path_values)

    if not count:
      if self.__max != 0:
        return MissingValueCardinalityResult(
            obj, valid=False,
            cardinality_pred=self, path_pred_result=collected_result)
      else:
        result_type = ConfirmedCardinalityResult

    elif self.__max == 0:
      result_type = UnexpectedValueCardinalityResult

    elif (count >= self.__min
          and (self.__max is None or count <= self.__max)):
      result_type = ConfirmedCardinalityResult

    else:
      result_type = FailedCardinalityRangeResult

    valid = result_type == ConfirmedCardinalityResult

    return result_type(valid=valid, cardinality_pred=self,
                       path_pred_result=collected_result)
