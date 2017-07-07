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

"""Fine grained matching of individual elements within a compound type.

For example specifying predicates for individual elements within a dictionary.
"""

from .base_binary_predicate import BinaryPredicate
from .keyed_predicate_result import KeyedPredicateResultBuilder
from .map_predicate import MapPredicate
from .path_predicate import PathPredicate
from .path_value import PathValue
from .path_result import (
    TypeMismatchError,
    UnexpectedPathError)
from .sequenced_predicate_result import SequencedPredicateResultBuilder


class DictMatchesPredicate(BinaryPredicate):
  """Implements binary predicate comparison predicates against dict values.

  The dictionary value is in the form {field : pred} where each element
  in the dictionary is a predicate for validating that particular field.
  A strict predicate means that exactly all specified fields must be present.
  Otherwise this permits additional fields with arbitrary values.

  For example (using the json_predicate aliases EQUIVALENT and CONTAINS):
      DictMatcherPredicate({'n' : EQUIVALENT(10), 's' : CONTAINS('text')})
  would want a field with n=10 and s having 'text' as a substring.
  """

  @property
  def strict(self):
    """Whether only the specified fields may be present (True) or not."""
    return self.__strict

  def __init__(self, operand, **kwargs):
    """Constructor."""
    if not isinstance(operand, dict):
      raise TypeError(
          '{0} is not a dict: {1!r}'.format(operand.__class__, operand))
    self.__strict = kwargs.pop('strict', False)
    super(DictMatchesPredicate, self).__init__('Matches', operand, **kwargs)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    entity.add_metadata('strict', self.__strict)
    for key, pred in self.operand.items():
      snapshot.edge_builder.make_control(entity, key, pred)

  def __eq__(self, obj):
    return (super(DictMatchesPredicate, self).__eq__(obj)
            and self.__strict == obj.strict)

  def __call__(self, context, value):
    """Implements Predicate interface.

    context: [ExecutionContext] The execution context.
    value: [dict] The dictionary to match against our operand.

    Returns a KeyedPredicateResult indicating each of the fields.
    """
    if not isinstance(value, dict):
      return TypeMismatchError(dict, value.__class__, value)

    match_result_builder = KeyedPredicateResultBuilder(self)
    valid = True
    for key, pred in self.operand.items():
      name = context.eval(key)
      name_result = PathPredicate(key, pred, source_pred=pred,
                                  enumerate_terminals=False)(context, value)
      if not name_result:
        valid = False
      match_result_builder.add_result(name, name_result)

    if self.strict:
      # Only consider and add strictness result if it fails
      strictness_errors = self._find_unexpected_path_errors(context, value)
      if strictness_errors:
        valid = False
        match_result_builder.update_results(strictness_errors)

    return match_result_builder.build(valid)

  def _find_unexpected_path_errors(self, context, source):
    """Check value keys for unexpected ones.

    Args:
      context: [ExecutionContext] The execution context.
      source: [dict] The dictionary to match against our operand.

    Returns:
      dictionary of errors keyed by unexpected path.
    """
    # pylint: disable=unused-argument
    errors = {}
    expect_keys = self.operand.keys()
    for key, value in source.items():
      if key not in expect_keys:
        errors[key] = UnexpectedPathError(source=source, target_path=key,
                                          path_value=PathValue(key, value))
    return errors


class ListMatchesPredicate(BinaryPredicate):
  """Implements binary predicate comparison predicates against list values.

  Each element of the operand is a predicate that validates each element in the
  called value list. If the predicate is strict, then each value must match a
  predicate in the operand. If the predicate is unique then each value must only
  match one predicate.
  """

  @property
  def strict(self):
    """Whether all the elements must satisfy a predicate (True) or not."""
    return self.__strict

  @property
  def unique(self):
    """Whether a given element complies with at most one (True) predicates."""
    return self.__unique

  def __init__(self, operand, **kwargs):
    """Constructor."""
    if not isinstance(operand, list):
      raise TypeError(
          '{0} is not a list: {1!r}'.format(operand.__class__, operand))
    self.__strict = kwargs.pop('strict', False)
    self.__unique = kwargs.pop('unique', False)
    super(ListMatchesPredicate, self).__init__('Matches', operand, **kwargs)

  def __eq__(self, obj):
    return (super(ListMatchesPredicate, self).__eq__(obj)
            and self.__unique == obj.unique
            and self.__strict == obj.strict)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    entity.add_metadata('strict', self.__strict)
    entity.add_metadata('unique', self.__unique)
    for index, pred in enumerate(self.operand):
      key = '[{0}]'.format(index)
      snapshot.edge_builder.make_control(entity, key, pred)

  def __call__(self, context, value):
    """Implements Predicate interface.

    context: [ExecutionContext] The execution context.
    value: [list] The value list to match against our operand.

    Returns a SequencedPredicateResult indicating each of the fields.
    """
    if not isinstance(value, list):
      return TypeMismatchError(list, value.__class__, value)

    if self.__unique:
      max_count = 1
    else:
      max_count = None

    match_result_builder = SequencedPredicateResultBuilder(self)
    valid = True
    matched_element_count = [0] * len(value)
    for match_pred in self.operand:
      pred_result = MapPredicate(match_pred, max=max_count)(context, value)
      match_result_builder.append_result(pred_result)
      if not pred_result:
        valid = False
      for index in range(len(value)):
        matched_element_count[index] += 1 if pred_result.results[index] else 0

    if self.strict:
      # Only consider and add strictness result if it fails
      strictness_errors = self._find_strictness_errors(
          matched_element_count, value)
      if strictness_errors:
        valid = False
        match_result_builder.extend_results(strictness_errors)

    return match_result_builder.build(valid)

  def _find_strictness_errors(self, matched_element_count, source):
    """Check for each element being matched

    Args:
      matched_element_count: [list] number of matched predicates in source.
      source: [list] The list to match against our operand.

    Returns:
      list of unmatched source values.
    """
    # pylint: disable=unused-argument
    errors = []
    for index, count in enumerate(matched_element_count):
      if count == 0:
        path = '[{0}]'.format(index)
        errors.append(
            UnexpectedPathError(source=source, target_path=path,
                                path_value=PathValue(path, source[index])))
    return errors


DICT_MATCHES = DictMatchesPredicate
LIST_MATCHES = ListMatchesPredicate
