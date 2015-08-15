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
    return self._pred

  @property
  def count(self):
    return self._count

  def summary_string(self):
    raise NotImplemented('{0}.summary_string not implemented.'.format(
            self.__class__))

  def _make_scribe_parts(self, scribe):
    count_relation = scribe.part_builder.determine_verified_relation(self)
    result_relation = scribe.part_builder.determine_verified_relation(
        self._pred_result)
    return [scribe.build_part('Count', self._count, relation=count_relation),
            scribe.part_builder.build_mechanism_part('Predicate', self._pred),
            scribe.part_builder.build_input_part('Source', self._source),
            scribe.part_builder.build_nested_part('Result', self._pred_result,
                                                  relation=result_relation)]

  def __init__(self, source, count, pred, pred_result, valid=False):
    super(CardinalityResult, self).__init__(valid)
    self._source = source
    self._count = count
    self._pred = pred
    self._pred_result = pred_result

  def __str__(self):
    return '{0} detail={1}'.format(self.summary_string(), self._pred_result)

  def __eq__(self, event):
    return (self.__class__ == event.__class__
            and self._count == event._count
            and self._pred == event._pred
            and self._source == event._source
            and self._pred_result == event._pred_result)


class ConfirmedCardinalityResult(CardinalityResult):
  """Denotes a CardinalityPredicate that was satisfied."""

  def __init__(self, source, count, pred, pred_result, valid=True):
      super(ConfirmedCardinalityResult, self).__init__(
          valid=valid,
          source=source, count=count, pred=pred, pred_result=pred_result)

  def summary_string(self):
    if not self.count:
      return 'Confirmed no {value}.'.format(
          value=self.pred.predicate_string)

    return 'Confirmed pred={summary} with count={count}'.format(
        summary=self.pred, count=self._count)


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
    return self._map_pred.pred

  @property
  def min(self):
    return self._min

  @property
  def max(self):
    return self._max

  @property
  def predicate_string(self):
    return str(self.pred)

  def _make_scribe_parts(self, scribe):
    return [scribe.part_builder.build_mechanism_part('Predicate', self.pred),
            scribe.build_part('Min', self._min,
                              relation=scribe.part_builder.CONTROL),
            scribe.build_part('Max', 'Any' if self._max < 0 else self._max,
                              relation=scribe.part_builder.CONTROL)]

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

    self._map_pred = map_predicate.MapPredicate(pred, min=min, max=max)
    self._min = min
    self._max = max

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self._min == pred._min
            and self._max == pred._max
            and self._map_pred == pred._map_pred)

  def __str__(self):
    return '[{0}] {1}..{2}'.format(self.pred, self._min, self._max)

  def __call__(self, obj):
    """Attempt to match object.

    Args:
      obj: JSON object to match.

    Returns:
      PredicateResponse
    """
    map_pred_result = self._map_pred(obj)
    count = len(map_pred_result.good_object_result_mappings)

    if not count:
      if self._max == 0:
        result_type = ConfirmedCardinalityResult
      else:
        result_type = MissingValueCardinalityResult

    elif self._max == 0:
      result_type = UnexpectedValueCardinalityResult

    elif (count >= self._min
          and (self._max == None or count <= self._max)):
      result_type = ConfirmedCardinalityResult

    else:
      result_type = FailedCardinalityRangeResult

    valid = result_type == ConfirmedCardinalityResult

    return result_type(valid=valid, source=obj, count=count,
                       pred=self, pred_result=map_pred_result)
