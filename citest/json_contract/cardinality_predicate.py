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
from . import map_predicate


class CardinalityResult(predicate.PredicateResult):
  """Denotes a PredicateResult from a CardinalityPredicate.

  In practice, this is a base class that is further refined for specific
  types of events.

  Attributes:
    pred: The ValuePredicate genearting the result.
    found: A list of JSON objects the predicate was applied to.
        In practice these are the matched objects.
  """

  @property
  def pred(self):
    """The predicate we mapped over the collection."""
    return self.__pred

  @property
  def count(self):
    """The number of elements that satisfied the predicate."""
    return self.__count

  @property
  def source(self):
    """The source value (collection) that we are mapping the predicateover."""
    return self.__source

  @property
  def pred_result(self):
    """The result of mapping the underlying predicate over the source."""
    return self.__pred_result

  def summary_string(self):
    """A human readable string summarizing this result."""
    raise NotImplementedError('{0}.summary_string not implemented.'.format(
        self.__class__))

  def __init__(self, source, count, pred, pred_result, valid=False):
    """Constructor.

    Args:
      source: [any] The source value that we applied the predicate to.
      count: [int] The number of elements in the source satisfying predicate.
      pred: [CarindalityPredicate] The predicate applied to the source.
      pred_result: [PredicateResult]. The result of applying pred to source.
      valid: [bool] Whether or not the cardinality predicate was satisfied.
    """
    super(CardinalityResult, self).__init__(valid)
    self.__source = source
    self.__count = count
    self.__pred = pred
    self.__pred_result = pred_result

  def __str__(self):
    return '{summary} detail={detail}'.format(
        summary=self.summary_string(), detail=self.__pred_result)

  def __eq__(self, event):
    return (self.__class__ == event.__class__
            and self.__count == event.count
            and self.__pred == event.pred
            and self.__source == event.source
            and self.__pred_result == event.pred_result)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    count_relation = builder.determine_valid_relation(self)
    result_relation = builder.determine_valid_relation(self.__pred_result)
    builder.make(entity, 'Count', self.__count, relation=count_relation)
    builder.make_mechanism(entity, 'Predicate', self.__pred)
    builder.make_input(entity, 'Source', self.__source, format='json')
    builder.make(entity, 'Result', self.__pred_result, relation=result_relation)


class ConfirmedCardinalityResult(CardinalityResult):
  """Denotes a CardinalityPredicate that was satisfied."""

  def __init__(self, source, count, pred, pred_result, valid=True):
    """Constructor.

    Args:
      source: [any] The value we applied the cardinality predicate to.
      count: [number] The number of source values satisfying the predicate.
      pred: [ValuePredicate] The predicate we applied to each source value.
      pred_results: [PredicateResult] The results from applying the predicate.
      value [boolean]: Whether the cardinality was satisifed or not.
    """
    super(ConfirmedCardinalityResult, self).__init__(
        source=source, count=count, pred=pred, pred_result=pred_result,
        valid=valid)

  def summary_string(self):
    """Returns human-readable summary of this result."""
    if not self.count:
      return 'Confirmed no {value}.'.format(
          value=self.pred.predicate_string)

    return 'Confirmed pred={summary} with count={count}'.format(
        summary=self.pred, count=self.count)


class FailedCardinalityResult(CardinalityResult):
  """Denotes a CardinalityPredicate that was not satisfied.

  In practice, this is a base class used to detect failures.
  It is further specialized for the particular reason for failure.
  """
  pass


class UnexpectedValueCardinalityResult(FailedCardinalityResult):
  """Denotes a failure because a value existed where none were expected."""

  def summary_string(self):
    return 'Found unexpected {summary}: count={count}.'.format(
        summary=self.pred.predicate_string,
        count=self.count)


class MissingValueCardinalityResult(FailedCardinalityResult):
  """Denotes a failure because a value did not exist where one was expected."""

  def __init__(self, source, pred, pred_result, valid=True, count=0):
    super(MissingValueCardinalityResult, self).__init__(
        valid=valid,
        source=source, count=count, pred=pred, pred_result=pred_result)

  # pred is a CardinalityPredicate
  def summary_string(self):
    return 'Expected to find {pred} {min}..{max}.'.format(
        pred=self.pred.predicate_string, min=self.pred.min, max=self.pred.max)


class FailedCardinalityRangeResult(FailedCardinalityResult):
  """Denotes a failure because too few or too many values were found."""

  def summary_string(self):
    # pred is a CardinalityPredicate
    return ('Found {count} {criteria}'
            ' but expected {min}..{max}'.format(
                count=self.count, criteria=self.pred.predicate_string,
                min=self.pred.min, max=self.pred.max))


class CardinalityPredicate(predicate.ValuePredicate):
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
  def pred(self):
    """The underlying predicate that we are mapping."""
    return self.__map_pred.pred

  @property
  def min(self):
    """The minimum desired cardinality, or None for no lower bound."""
    return self.__min

  @property
  def max(self):
    """The maximum desired cardinality, or None for no upper bound."""
    return self.__max

  @property
  def _map_pred(self):
    """For internal use, the MapPredicate wrapping the underlying predicate."""
    return self.__map_pred

  @property
  def predicate_string(self):
    """A human-readable form of the predicate being mapped."""
    return str(self.pred)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self.pred)
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

    self.__map_pred = map_predicate.MapPredicate(pred, min=min, max=max)
    self.__min = min
    self.__max = max

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__min == pred.min
            and self.__max == pred.max
            and self._map_pred == pred._map_pred)

  def __str__(self):
    return '[{0}] {1}..{2}'.format(self.pred, self.__min, self.__max)

  def __call__(self, obj):
    """Attempt to match object.

    Args:
      obj: JSON object to match.

    Returns:
      PredicateResponse
    """
    map_pred_result = self.__map_pred(obj)
    count = len(map_pred_result.good_object_result_mappings)

    if not count:
      if self.__max == 0:
        result_type = ConfirmedCardinalityResult
      else:
        result_type = MissingValueCardinalityResult

    elif self.__max == 0:
      result_type = UnexpectedValueCardinalityResult

    elif (count >= self.__min
          and (self.__max == None or count <= self.__max)):
      result_type = ConfirmedCardinalityResult

    else:
      result_type = FailedCardinalityRangeResult

    valid = result_type == ConfirmedCardinalityResult

    return result_type(valid=valid, source=obj, count=count,
                       pred=self, pred_result=map_pred_result)
