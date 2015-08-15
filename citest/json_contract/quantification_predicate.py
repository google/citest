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

class UniversalOrExistentialPredicateFactory(object):
  """Creates either universal or existential predicates."""

  def __init__(self, is_universal, elem_pred_factory):
    self._is_universal = is_universal
    self._elem_pred_factory = elem_pred_factory

  def __call__(self, operand):
    return UniversalOrExistentialPredicate(
        self._is_universal, self._elem_pred_factory(operand))


class UniversalOrExistentialPredicate(predicate.ValuePredicate):
  """Makes bound predicate either universal or existential on members of a list.

  If the value is not a list, then apply the bound element predicate on
  the value itself.

  Attributes:
    element_pred:  ValuePredicate to apply to elements of list values.
        The existential predicate is valid when the element_pred is satisfied
        by one or more list value elements against the provided operand.
    is_existential: True if this acts as an existential predicate
        An existential predicate will accept values when the bound element_pred
        accepts at least one element of a value list (or the non-list
        value). Once an existential predicate finds a valid element, it will
        stop iterating over the value list elements.
        This is the complement of is_universal.
    is_universal: True if this acts as a universal predicate.
        A universal predicate will accept values when the bound element_pred
        accepts all the individual elements of the value list (or the non-list
        value). This is the complement of is_existential.
  """

  @property
  def element_pred(self):
    return self._element_pred

  @property
  def is_existential(self):
    return not self._is_universal

  @property
  def is_universal(self):
    return self._is_universal

  def __init__(self, is_universal, element_pred):
    self._is_universal = is_universal
    self._element_pred = element_pred
    self._name = 'All' if is_universal else 'Exists'

  def __str__(self):
    return '{0}({1})'.format(self._name, self._element_pred)

  def __eq__(self, op):
    return (self.__class__ == op.__class__
            and self._is_universal == op._is_universal
            and self._element_pred == op._element_pred)

  def _apply_existential(self, value):
    """Helper function that interprets predicate as existential predicate.

    Returns:
      Either all the good results or all the bad results depending on whether
      any good_results were found.
    """

    valid = False
    good_builder = predicate.CompositePredicateResultBuilder(self)
    bad_builder = predicate.CompositePredicateResultBuilder(self)

    for elem in value:
      if isinstance(elem, list):
        result = self(elem)
      else:
        result = self._element_pred(elem)

      if result:
        good_builder.append_result(result)
        valid = True
      else:
        bad_builder.append_result(result)

    return (good_builder if valid else bad_builder).build(valid)


  def _apply_universal(self, value):
    """Helper function that interprets predicate as universal predicate."""

    builder = predicate.CompositePredicateResultBuilder(self)
    valid = True
    for elem in value:
      result = self._element_pred(elem)
      builder.append_result(result)
      if not result:
        valid = False

    return builder.build(valid)

  def __call__(self, value):
    if not isinstance(value, list):
      return self._element_pred(value)

    if self._is_universal:
      return self._apply_universal(value)
    else:
      return self._apply_existential(value)
