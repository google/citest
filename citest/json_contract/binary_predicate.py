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


import inspect

from . import path_predicate_result as jc
from . import predicate
from . import quantification_predicate as qp


class BinaryPredicate(predicate.ValuePredicate):
  """
  Attributes:
    name: The name of the predicate is used to specify the particular
        comparison predicate to use. The supported names are:
    operand: The operand to compare against. This is the RHS of the predicate.
  """
  @property
  def name(self):
    return self._name

  @property
  def operand(self):
    return self._operand

  def __str__(self):
    return '{0}({1} {2!r})'.format(
        self.__class__.__name__, self._name, self._operand)

  def __init__(self, name, operand):
    self._name = name
    self._operand = operand

  def __eq__(self, op):
    return (self.__class__ == op.__class__
            and self._name == op._name
            and self._operand == op._operand)

  def _make_scribe_parts(self, scribe):
    # Do not inherit from the base class because it will add our string
    # value, which would be superfluous.
    parts = [scribe.build_part('Name', self._name),
             scribe.build_part('Operand', self._operand,
                               relation=scribe.part_builder.CONTROL)]
    return parts


class StandardBinaryPredicateFactory(object):
  """Create a StandardBinaryPredicate once we have an operand to bind to it."""

  def __init__(self, name, comparison_op, operand_type=None):
    """Constructor.

    Args:
      name: Name of the comparison_op
      comparison_op: Callable that takes (value, operand) and returns bool.
      operand_type: Class expected for operands, or None to not enforce.
    """
    self._type = operand_type
    self._name = name
    self._comparison_op = comparison_op

  def __call__(self, operand):
    return StandardBinaryPredicate(
        self._name, self._comparison_op, operand, operand_type=self._type)


class StandardBinaryPredicate(BinaryPredicate):
  """A BinaryPredicate using a bool predicate bound at construction."""

  def __init__(self, name, comparison_op, operand, operand_type=None):
    """Constructor.

    Args:
      name: Name of predicate
      comparison_op: Implements bool predicate
      operand: Value to bind to predicate.
      operand_type: Class to enforce for operands, or None to not enforce.
    """
    if operand_type and not isinstance(operand, operand_type):
      raise TypeError(
          '{0} is not {1}: {1!r}', operand.__class__, operand_type, operand)
    super(StandardBinaryPredicate, self).__init__(name, operand)
    self._type = operand_type
    self._comparison_op = comparison_op

  def __str__(self):
    if self._type == None:
      type_name = 'Any'
    if inspect.isclass(self._type):
      type_name = self._type.__name__
    else:
      type_name = str(self._type)
    return '{0}.{1}({2!r})'.format(type_name, self._name, self.operand)

  def __call__(self, value):
    if self._type and not isinstance(value, self._type):
      return jc.JsonTypeMismatchResult(self._type, value.__class__, value)

    valid = self._comparison_op(value, self.operand)
    return jc.JsonFoundValueResult(value=value, valid=valid, pred=self)


class DictSubsetPredicate(BinaryPredicate):
  """Implements binary predicate comparison predicates against dict values."""

  def __init__(self, operand):
    if not isinstance(operand, dict):
      raise TypeError(
          '{0} is not a dict: {1!r}'.format(operand.__class__, operand))
    super(DictSubsetPredicate, self).__init__('has-subset', operand)

  def __call__(self, value):
    if not isinstance(value, dict):
      return jc.JsonTypeMismatchResult(dict, value.__class__, value)
    return self._is_subset(value, None, self.operand, value)

  def _is_subset(self, source, path, a, b):
    """Determine if |a| is a subset of |b|."""

    ## FOR EACH element of operand...
    for name, a_value in a.items():
      namepath = '{0}/{1}'.format(path, name) if path else name
      try:
        b_value = b[name]
      except KeyError as e:
        ## IF element was not in |b| then it is not a subset.
        return jc.JsonMissingPathResult(source, namepath)

      # IF the element is itself a dictionary
      # THEN recurse to ensure |a_item| is a subset of |b_item|.
      if isinstance(b_value, dict):
        result = self._is_subset(source, namepath, a_value, b_value)
        if not result:
          return result
        continue

      # IF the element is a list
      # THEN ensure that |a_item| is a subset of |b_item|.
      if isinstance(b_value, list):
        elem_pred = (LIST_SUBSET
                       if isinstance(a_value, list)
                       else qp.UniversalOrExistentialPredicateFactory(
                           False, CONTAINS))
        result = elem_pred(a_value)(b_value)
        if not result:
          return result.clone_with_new_context(source, namepath)
        continue

      # Otherwise, we want an exact match.
      # Seems practical for what's intended.
      # If individual fields want different types of matches,
      # then they can call themselves out into a different PathFinder
      # that specifies the individual fields rather than a container.
      if a_value != b_value:
        if isinstance(b_value, basestring):
          pred_factory = STR_EQ
        elif isinstance(b_value, (int, long, float)):
          pred_factory = NUM_EQ
        else:
          pred_factory = EQUIVALENT

        return jc.JsonFoundValueResult(
            valid=False, pred=pred_factory(a_value),
            source=source, path=namepath, value=b_value)

    return jc.JsonFoundValueResult(
        valid=True, source=source, path=path, value=b, pred=self)


class _BaseListMembershipPredicate(BinaryPredicate):
  """Implements binary predicate comparison predicate for list membership."""

  @property
  def strict(self):
    return self.__strict

  def __init__(self, name, operand, strict=False):
    self.__strict = strict
    super(_BaseListMembershipPredicate, self).__init__(name, operand)

  def _verify_elem(self, elem, the_list):
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
      return elem in the_list

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
      if pred(value):
        return True

    return False
  

class ListSubsetPredicate(_BaseListMembershipPredicate):
  """Implements binary predicate comparison predicate for list subsets."""

  def __init__(self, operand, strict=False):
    if not isinstance(operand, list):
        raise TypeError(
            '{0} is not a list: {1!r}'.format(operand.__class__, operand))
    super(ListSubsetPredicate, self).__init__(
        'has-subset', operand, strict=strict)

  def __call__(self, value):
    """Determine if |operand| is a subset of |value|."""
    if not isinstance(value, list):
      return jc.JsonTypeMismatchResult(list, value.__class__, value)

    for index, elem in enumerate(self.operand):
      if not self._verify_elem(elem, the_list=value):
         return jc.JsonFoundValueResult(value=value, valid=False, pred=self)

    return jc.JsonFoundValueResult(
        valid=True, source=None, path=None, value=value, pred=self)


class ListMembershipPredicate(_BaseListMembershipPredicate):
  """Implements binary predicate comparison predicate for list membership."""

  def __init__(self, operand, strict=False):
    super(ListMembershipPredicate, self).__init__(
        'has-elem', operand, strict=strict)

  def __call__(self, value):
    """Determine if |operand| is a member of |value|."""
    valid = self._verify_elem(self.operand, the_list=value)
    return jc.JsonFoundValueResult(
        valid=valid, source=None, path=None, value=value, pred=self)


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

  def __init__(self, operand):
    super(ContainsPredicate, self).__init__('Contains', operand)

  def __call__(self, value):
    if isinstance(value, basestring):
      return STR_SUBSTR(self._operand)(value)
    if isinstance(value, dict):
      return DICT_SUBSET(self._operand)(value)
    if isinstance(value, int or long or float):
      return NUM_EQ(self._operand)(value)
    if not isinstance(value, list):
      raise NotImplementedError(
          'Unhandled value class {0}'.format(value.__class__))
    if isinstance(self._operand, list):
      return LIST_SUBSET(self._operand)(value)

    # The value is a list but operand is not a list.
    # So we'll look for existance of the operand in the list
    # by recursing on each element of the list until we find something
    # or exhaust the list.
    bad_values = []
    for elem in value:
      result = self(elem)
      if result:
        return result
      bad_values.append(elem)

    return jc.JsonFoundValueResult(valid=False, pred=self,
                                   source=value, value=bad_values)


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

  def __init__(self, operand):
    super(ContainsPredicate, self).__init__('Contains', operand)

  def __call__(self, value):
    if isinstance(value, basestring):
      return STR_SUBSTR(self._operand)(value)
    if isinstance(value, dict):
      return DICT_SUBSET(self._operand)(value)
    if isinstance(value, int or long or float):
      return NUM_EQ(self._operand)(value)
    if not isinstance(value, list):
      raise NotImplementedError(
          'Unhandled value class {0}'.format(value.__class__))
    if isinstance(self._operand, list):
      return LIST_SUBSET(self._operand)(value)

    # The value is a list but operand is not a list.
    # So we'll look for existance of the operand in the list
    # by recursing on each element of the list until we find something
    # or exhaust the list.
    bad_values = []
    for elem in value:
      result = self(elem)
      if result:
        return result
      bad_values.append(elem)

    return jc.JsonFoundValueResult(valid=False, pred=self,
                                   source=value, value=bad_values)


class EquivalentPredicate(BinaryPredicate):
  """Specifies a predicate that expects the value and operand are "equal".

  This is similar to the type-specific '==' predicate, but is polymorphic.
  """

  def __init__(self, operand):
    super(EquivalentPredicate, self).__init__('Equivalent', operand)

  def _check_operand_and_call(self, type, value, pred_factory):
    if not isinstance(self._operand, type):
      return jc.JsonTypeMismatchResult(type, self._operand.__class__, value)
    return pred_factory(self._operand)(value)

  def __call__(self, value):
    if isinstance(value, basestring):
      return self._check_operand_and_call(basestring, value, STR_EQ)
    if isinstance(value, dict):
      return self._check_operand_and_call(dict, value, DICT_EQ)
    if isinstance(value, list):
      return self._check_operand_and_call(list, value, LIST_EQ)
    if isinstance(value, int or long or float):
      return self._check_operand_and_call((int, long, float), value, NUM_EQ)
    raise NotImplementedError(
        'Unhandled value class {0}'.format(value.__class__))


class DifferentPredicate(BinaryPredicate):
  """Specifies a predicate that expects the value and operand are not "equal".

  This is similar to the type-specific '!=' predicate, but is polymorphic.
  """

  def __init__(self, operand):
    super(DifferentPredicate, self).__init__('Different', operand)

  def _check_operand_and_call(self, type, value, pred_factory):
    if not isinstance(self._operand, type):
      return jc.JsonTypeMismatchResult(type, self._operand.__class__, value)
    return pred_factory(self._operand)(value)

  def __call__(self, value):
    if isinstance(value, basestring):
      return self._check_operand_and_call(basestring, value, STR_NE)
    if isinstance(value, dict):
      return self._check_operand_and_call(dict, value, DICT_NE)
    if isinstance(value, list):
      return self._check_operand_and_call(list, value, LIST_NE)
    if isinstance(value, int or long or float):
      return self._check_operand_and_call((int, long, float), value, NUM_NE)
    raise NotImplementedError(
        'Unhandled value class {0}'.format(value.__class__))


NUM_LE = StandardBinaryPredicateFactory(
    '<=', lambda a, b: a <= b, operand_type=(int, long, float))
NUM_GE = StandardBinaryPredicateFactory(
    '>=', lambda a, b: a >= b, operand_type=(int, long, float))
NUM_EQ = StandardBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=(int, long, float))
NUM_NE = StandardBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=(int, long, float))

STR_SUBSTR = StandardBinaryPredicateFactory(
    'has-substring', lambda a, b: a.find(b) >= 0, operand_type=basestring)
STR_EQ = StandardBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=basestring)
STR_NE = StandardBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=basestring)

DICT_EQ = StandardBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=dict)
DICT_NE = StandardBinaryPredicateFactory(
    '==', lambda a, b: a != b, operand_type=dict)
DICT_SUBSET = lambda operand: DictSubsetPredicate(operand)

LIST_EQ = StandardBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=list)
LIST_NE = StandardBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=list)
LIST_MEMBER = (lambda operand, strict=False:
                 ListMembershipPredicate(operand, strict=strict))
LIST_SUBSET = (lambda operand, strict=False:
                 ListSubsetPredicate(operand, strict=strict))

CONTAINS = ContainsPredicate
EQUIVALENT = EquivalentPredicate
DIFFERENT = DifferentPredicate
