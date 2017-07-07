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

"""Binary predicates define a predicate relating the value to a fixed operand.

For example a comparator operation that compares a given value against a
reference point. The reference point would be the fixed operand, and the given
value would be the value that the base interface is given to apply the
predicate to.
"""


from .base_binary_predicate import BinaryPredicate
from .simple_binary_predicate import (
    SimpleBinaryPredicateFactory,
    DICT_EQ,
    DICT_NE,
    LIST_NE,
    NUM_EQ,
    NUM_NE,
    STR_EQ,
    STR_NE,
    STR_SUBSTR)

from .path_value import PathValue
from .path_predicate import PathPredicate
from .path_result import (
    MissingPathError,
    PathValueResult,
    TypeMismatchError)


class DictSubsetPredicate(BinaryPredicate):
  """Implements binary predicate comparison predicates against dict values."""

  def __init__(self, operand, **kwargs):
    if not (isinstance(operand, dict) or callable(operand)):
      raise TypeError(
          '{0} is not a dict: {1!r}'.format(operand.__class__, operand))
    super(DictSubsetPredicate, self).__init__('has-subset', operand,
                                              operand_type=dict, **kwargs)

  def __call__(self, context, value):
    if not isinstance(value, dict):
      return TypeMismatchError(dict, value.__class__, value)
    operand = self.eval_context_operand(context)
    return self._is_subset(context, value, '', operand, value)

  def _is_subset(self, context, source, path, a, b):
    """Determine if |a| is a subset of |b|.

    Args:
      context: [ExecutionContext]
      source: [obj] The JSON object containing |a|.
      path: [string] The path to |a| from |source|.
      a: |obj| The JSON object that should be a subset of |b|.
      b: |obj| The JSON object that shuld be a superset of |a|.
    """
    # pylint: disable=invalid-name

    ## FOR EACH element of operand...
    for name, a_value in a.items():
      namepath = '{0}/{1}'.format(path, name) if path else name
      try:
        b_value = b[name]
      except KeyError:
        ## IF element was not in |b| then it is not a subset.
        return MissingPathError(source=source, target_path=namepath,
                                path_value=PathValue(path, b))

      # IF the element is itself a dictionary
      # THEN recurse to ensure |a_item| is a subset of |b_item|.
      if isinstance(b_value, dict):
        result = self._is_subset(context, source, namepath, a_value, b_value)
        if not result:
          return result
        continue

      # IF the element is a list
      # THEN ensure that |a_item| is a subset of |b_item|.
      if isinstance(b_value, list):
        elem_pred = LIST_SUBSET if isinstance(a_value, list) else CONTAINS
        result = elem_pred(a_value)(context, b_value)
        if not result:
          return result.clone_with_source(
              source=source, base_target_path=namepath, base_value_path=name)
        continue

      # Up until now we never used a_value directly.
      a_value = context.eval(a_value)

      # Otherwise, we want an exact match.
      # Seems practical for what's intended.
      # If individual fields want different types of matches,
      # then they can call themselves out into a different PathFinder
      # that specifies the individual fields rather than a container.

      if a_value != b_value:
        if isinstance(b_value, basestring):
          pred_factory = STR_EQ
          confirm_type = basestring
        elif isinstance(b_value, (int, long, float)):
          pred_factory = NUM_EQ
          confirm_type = (int, long, float)
        else:
          pred_factory = EQUIVALENT
          confirm_type = None

        if confirm_type is not None and not isinstance(a_value, confirm_type):
          return TypeMismatchError(confirm_type, a_value.__class__,
                                   source=source, target_path=namepath,
                                   path_value=PathValue(path, b))
        return PathValueResult(
            pred=pred_factory(a_value), source=source, target_path=namepath,
            path_value=PathValue(namepath, b_value), valid=False)

    return PathValueResult(
        pred=self, source=source, target_path=path,
        path_value=PathValue(path, b), valid=True)


class _BaseListMembershipPredicate(BinaryPredicate):
  """Implements binary predicate comparison predicate for list membership."""
  # pylint: disable=abstract-method

  @property
  def strict(self):
    """Strict membership means all members must satisfy the predicate."""
    return self.__strict

  def __init__(self, name, operand, **kwargs):
    """Constructor."""
    self.__strict = kwargs.pop('strict', False)
    super(_BaseListMembershipPredicate, self).__init__(name, operand, **kwargs)

  def _verify_elem(self, context, elem, the_list):
    """Verify if |elem| is in |the_list|

    Args:
      elem [object]: The value to test.
      the_list [list]: The list of objects to test against.

    Returns:
      True if the value is a member of the list or strict checking is disabled
           and the value is a subset of a member of the list.
      False otherwise.
    """
    if self.__strict or isinstance(elem, (int, long, float, basestring)):
      return elem in context.eval(the_list)

    if self.__strict:
      return False

    pred = None
    if isinstance(elem, list):
      pred = LIST_SUBSET(elem)
    elif isinstance(elem, dict):
      pred = DICT_SUBSET(elem)
    else:
      raise TypeError('Unhandled type {0}'.format(elem.__class__))

    for value in the_list:
      if pred(context, value):
        return True

    return False


class ListSubsetPredicate(_BaseListMembershipPredicate):
  """Implements binary predicate comparison predicate for list subsets."""

  def __init__(self, operand, **kwargs):
    if not isinstance(operand, list):
      raise TypeError(
          '{0} is not a list: {1!r}'.format(operand.__class__, operand))
    super(ListSubsetPredicate, self).__init__('has-subset', operand, **kwargs)

  def __call__(self, context, value):
    """Determine if |operand| is a subset of |value|."""
    if not isinstance(value, list):
      return TypeMismatchError(list, value.__class__, value)

    for elem in self.eval_context_operand(context):
      if not self._verify_elem(context, elem, the_list=value):
        return PathValueResult(pred=self, valid=False,
                               path_value=PathValue('', value),
                               source=value, target_path='')

    return PathValueResult(
        pred=self, valid=True, path_value=PathValue('', value),
        source=value, target_path='')


class ListMembershipPredicate(_BaseListMembershipPredicate):
  """Implements binary predicate comparison predicate for list membership."""

  def __init__(self, operand, **kwargs):
    super(ListMembershipPredicate, self).__init__(
        'has-elem', operand, **kwargs)

  def __call__(self, context, value):
    """Determine if |operand| is a member of |value|."""
    valid = self._verify_elem(context, self.operand, the_list=value)
    return PathValueResult(
        pred=self, valid=valid, source=value, target_path='',
        path_value=PathValue('', value))


class ContainsPredicate(BinaryPredicate):
  """Specifies a predicate that expects the value "contains" the operand.

  The interpretation of "contains" depends on the value's type:
        type        | operand interpretation
        ------------+-----------------------
        basestring  | 'is-substring-of'
        dict        | 'is-subset-of'
        list        | 'is-subset-of' if operand is a list.
                    | EXISTS and element that CONTAINS operand otherwise.
        numeric     | '=='
  """

  def __init__(self, operand, **kwargs):
    super(ContainsPredicate, self).__init__('Contains', operand, **kwargs)

  def __call__(self, context, value):
    if isinstance(value, basestring):
      return STR_SUBSTR(self.operand)(context, value)
    if isinstance(value, dict):
      return DICT_SUBSET(self.operand)(context, value)
    if isinstance(value, int or long or float):
      return NUM_EQ(self.operand)(context, value)
    if not isinstance(value, list):
      raise NotImplementedError(
          'Unhandled value class {0}'.format(value.__class__))
    if isinstance(self.operand, list):
      return LIST_SUBSET(self.operand)(context, value)

    # The value is a list but operand is not a list.
    # So we'll look for existance of the operand in the list
    # by recursing on each element of the list until we find something
    # or exhaust the list.
    bad_values = []
    for elem in value:
      result = self(context, elem)
      if result:
        return result
      bad_values.append(elem)

    return PathValueResult(valid=False, pred=self,
                           source=value, target_path='',
                           path_value=PathValue('', bad_values))


class EquivalentPredicate(BinaryPredicate):
  """Specifies a predicate that expects the value and operand are "equal".

  This is similar to the type-specific '==' predicate, but is polymorphic.
  """

  def __init__(self, operand, **kwargs):
    """Constructor.

    Args:
      operand: [any] The value to compare the argument against.

      See base class (BinaryPredicate) for additional kwargs.
    """
    super(EquivalentPredicate, self).__init__('Equivalent', operand, **kwargs)

  def __check_operand_and_call(self, context, operand_type,
                               value, pred_factory):
    """Ensure the operand is of the expected type and apply the predicate.

    Args:
      operand_type: [type] The type we expect the operand to be.
      value: [any] The value we want to apply the predicate to.
      pred_factory: [method] Given the operand, constructs a binary predicate
         that performs a == comparision and returns a PredicateResult.
    Returns
      PredicateResult might be JsonTypeMismatchResult if operand_type is wrong.
    """
    operand = context.eval(self.operand)
    if not isinstance(operand, operand_type):
      return TypeMismatchError(operand_type, operand.__class__, value)
    return pred_factory(operand)(context, value)

  def __call__(self, context, value):
    """Implements the predicate by determining if value == operand."""
    if isinstance(value, basestring):
      return self.__check_operand_and_call(context, basestring, value, STR_EQ)
    if isinstance(value, dict):
      return self.__check_operand_and_call(context, dict, value, DICT_EQ)
    if isinstance(value, list):
      return self.__check_operand_and_call(context, list, value, LIST_SIMILAR)
    if isinstance(value, int or long or float):
      return self.__check_operand_and_call(context, (int, long, float),
                                           value, NUM_EQ)
    raise NotImplementedError(
        'Unhandled value class {0}'.format(value.__class__))


class DifferentPredicate(BinaryPredicate):
  """Specifies a predicate that expects the value and operand are not "equal".

  This is similar to the type-specific '!=' predicate, but is polymorphic.
  """

  def __init__(self, operand, **kwargs):
    """Constructor.

    Args:
      operand: [any] The value to compare the argument against.

      See base class (BinaryPredicate) for additional kwargs.
    """
    super(DifferentPredicate, self).__init__('Different', operand, **kwargs)

  def __check_operand_and_call(self, context, operand_type,
                               value, pred_factory):
    """Ensure the operand is of the expected type and apply the predicate.

    Args:
      operand_type: [type] The type we expect the operand to be.
      value: [any] The value we want to apply the predicate to.
      pred_factory: [method] Given the operand, constructs a binary predicate
         that performs a != comparision and returns a PredicateResult.
    Returns
      PredicateResult might be JsonTypeMismatchResult if operand_type is wrong.
    """
    operand = context.eval(self.operand)
    if not isinstance(operand, operand_type):
      return TypeMismatchError(
          operand_type, operand.__class__, value)
    return pred_factory(operand)(context, value)

  def __call__(self, context, value):
    """Implements the predicate by determining if value != operand."""
    if isinstance(value, basestring):
      return self.__check_operand_and_call(context, basestring, value, STR_NE)
    if isinstance(value, dict):
      return self.__check_operand_and_call(context, dict, value, DICT_NE)
    if isinstance(value, list):
      return self.__check_operand_and_call(context, list, value, LIST_NE)
    if isinstance(value, int or long or float):
      return self.__check_operand_and_call(
          context, (int, long, float), value, NUM_NE)
    raise NotImplementedError(
        'Unhandled value class {0}'.format(value.__class__))


DICT_SUBSET = DictSubsetPredicate

def lists_equivalent(a, b):
  """Determine if two lists are equivalent without regard to order."""
  # pylint: disable=invalid-name
  if len(a) != len(b):
    return False
  sorted_a = sorted(a)
  sorted_b = sorted(b)
  for index, value in enumerate(sorted_a):
    if sorted_b[index] != value:
      return False
  return True

LIST_SIMILAR = SimpleBinaryPredicateFactory(
    '~=', lambda a, b: lists_equivalent(a, b), operand_type=list)
LIST_MEMBER = (lambda operand, strict=False:
               ListMembershipPredicate(operand, strict=strict))
LIST_SUBSET = (lambda operand, strict=False:
               ListSubsetPredicate(operand, strict=strict))

CONTAINS = ContainsPredicate
EQUIVALENT = EquivalentPredicate
DIFFERENT = DifferentPredicate
