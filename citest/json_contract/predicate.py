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


from ..base.scribe import Scribable
from ..base import JsonSnapshotable


class ValuePredicate(Scribable, JsonSnapshotable):
  """Base class denoting a predicate that determines if a JSON value is ok.

   This class must be specialized with a __call__ method that takes a single
   value object and returns None if the value is acceptable, or a JsonError
   explaining why it is not.

   The intent of this class is to check if a JSON object contains fields
   with particular values, ranges or other properties.
  """

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
    return str(self)

  def __ne__(self, op):
    return not self.__eq__(op)


class PredicateResult(Scribable, JsonSnapshotable):
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
    return '{name} ({valid})'.format(
        name=self.__class__.__name__,
        valid='GOOD' if self._valid else 'BAD')

  @property
  def comment(self):
    return self._comment

  @property
  def cause(self):
    return self._cause

  @property
  def valid(self):
    return self._valid

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder
    verified_relation = builder.determine_valid_relation(self._valid)
    builder.make(entity, 'Valid', self._valid, relation=verified_relation)
    if self._comment:
      builder.make(entity, 'Comment', self._comment)
    if self._cause:
      builder.make(entity, 'Cause', self._cause)

    # Set a default relation so that this can be picked up when it appears
    # as a list element.
    entity.add_metadata('_default_relation', verified_relation)

  def _make_scribe_parts(self, scribe):
    parts = []
    verified_relation = scribe.part_builder.determine_verified_relation(
        self._valid)
    parts.append(
        scribe.build_part('Valid', self._valid, relation=verified_relation))

    if self._comment:
      parts.append(scribe.build_part('Comment', self._comment))
    if self._cause:
      parts.append(scribe.build_part('Cause', self._cause))
    return parts

  def __init__(self, valid, comment="", cause=None):
    self._valid = valid
    self._comment = comment
    self._cause = cause

  def __repr__(self):
    return str(self)

  def __str__(self):
    return (self._comment
            or '{0} is {1}'.format(self.__class__.__name__,
                                   'OK' if self._valid else 'FAILURE'))

  def __nonzero__(self):
    return self._valid

  def __eq__(self, result):
    if (self.__class__ != result.__class__
        or self._valid != result._valid
        or self._comment != result._comment):
      return False

    # If cause was an exception then just compare classes.
    # Otherwise compare causes.
    # We assume cause is None, and Exception, or another PredicateResult.
    # Exceptions do not typically support value equality.
    if self._cause != result._cause:
      return (isinstance(self._cause, Exception)
              and self._cause.__class__ == result._cause.__class__)
    return self._cause == result._cause

  def __ne__(self, result):
    return not self.__eq__(result)


class CompositePredicateResult(PredicateResult):
  """Aggregates a collection of predicate results into a single response.

  Attributes:
    pred: The ValuePredicate doing the aggregation.
    results: The list of PredicateResponse instances being aggregated.
  """

  @property
  def pred(self):
    return self._pred

  @property
  def results(self):
    return self._results

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder
    summary = builder.object_count_to_summary(
        self._results, subject='mapped result')
    builder.make_mechanism(entity, 'Predicate', self._pred)
    builder.make(entity, '#', len(self._results))

    result_entity = snapshot.new_entity(summary='Composite Results')
    for index, result in enumerate(self._results):
        builder.make(result_entity, '[{0}]'.format(index), result,
                     relation=builder.determine_valid_relation(result),
                     summary=result.summary)
    builder.make(entity, 'Results', result_entity,
                 relation=builder.determine_valid_relation(self))
    super(CompositePredicateResult, self).export_to_json_snapshot(
        snapshot, entity)

  def _make_scribe_parts(self, scribe):
    parts = []
    parts.append(
        scribe.part_builder.build_mechanism_part('Predicate', self._pred))

    summary = scribe.make_object_count_summary(
        self._results, subject='mapped result')
    section = scribe.make_section(title=summary)
    section.parts.append(
      scribe.build_part('#', len(self._results)))
    for r in self._results:
      section.parts.append(
          scribe.part_builder.build_output_part(None, r, summary=r.summary))
    parts.append(scribe.build_part('Results', section))

    inherited = super(CompositePredicateResult, self)._make_scribe_parts(
        scribe)
    return parts + inherited

  def __str__(self):
    return '{0}'.format(self._results)

  def __init__(self, valid, pred, results, comment=None, cause=None):
    super(CompositePredicateResult, self).__init__(
        valid, comment=comment, cause=cause)
    self._pred = pred
    self._results = results

  def __eq__(self, result):
    return (self.__class__ == result.__class__
            and self._pred == result._pred
            and self._results == result._results)


class CompositePredicateResultBuilder(object):
  """Helper class for building a composite result."""

  def __init__(self, pred):
    self._pred = pred
    self.cause = None
    self.comment = None
    self._results = []

  def append_result(self, result):
    self._results.append(result)

  def extend_results(self, results):
    self._results.extend(results)

  def build(self, valid):
    return CompositePredicateResult(
        valid, self._pred, self._results, self.comment, self.cause)
