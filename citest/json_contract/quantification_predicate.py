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

"""Predicates for existential (exists) and universal (all) quanitification."""


from . import predicate


class UniversalOrExistentialPredicateFactory(object):
  """Creates either universal or existential predicates."""
  # pylint: disable=too-few-public-methods

  def __init__(self, is_universal, elem_pred_factory):
    self.__is_universal = is_universal
    self.__elem_pred_factory = elem_pred_factory

  def __call__(self, operand):
    return UniversalOrExistentialPredicate(
        self.__is_universal, self.__elem_pred_factory(operand))


class UniversalOrExistentialPredicate(predicate.ValuePredicate):
  """Makes bound predicate either universal or existential on members of a list.

  If the value is not a list, then apply the bound element predicate on
  the value itself.
  """

  @property
  def element_pred(self):
    """ValuePredicate to apply to elements of list values.

       The existential predicate is valid when the element_pred is satisfied
       by one or more list value elements against the provided operand.
    """
    return self.__element_pred

  @property
  def is_existential(self):
    """True if this acts as an existential predicate

       An existential predicate will accept values when the bound element_pred
       accepts at least one element of a value list (or the non-list
       value). Once an existential predicate finds a valid element, it will
       stop iterating over the value list elements.
       This is the complement of is_universal.
    """
    return not self.__is_universal

  @property
  def is_universal(self):
    """True if this acts as a universal predicate.

       A universal predicate will accept values when the bound element_pred
       accepts all the individual elements of the value list (or the non-list
       value). This is the complement of is_existential.
    """
    return self.__is_universal

  def __init__(self, is_universal, element_pred):
    self.__is_universal = is_universal
    self.__element_pred = element_pred
    self.__name = 'All' if is_universal else 'Exists'

  def __str__(self):
    return '{0}({1})'.format(self.__name, self.__element_pred)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__is_universal == pred.is_universal
            and self.__element_pred == pred.element_pred)

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder
    # 2200 is FORALL
    # 2203 is EXISTS
    builder.make_control(
        entity, 'Operator', u'\u2200' if self.__is_universal else u'\u2203')
    builder.make_mechanism(entity, 'Elem Pred', self.__element_pred)

  def __apply_existential(self, value):
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
        result = self.__element_pred(elem)

      if result:
        good_builder.append_result(result)
        valid = True
      else:
        bad_builder.append_result(result)

    return (good_builder if valid else bad_builder).build(valid)


  def __apply_universal(self, value):
    """Helper function that interprets predicate as universal predicate."""

    builder = predicate.CompositePredicateResultBuilder(self)
    valid = True
    for elem in value:
      result = self.__element_pred(elem)
      builder.append_result(result)
      if not result:
        valid = False

    return builder.build(valid)

  def __call__(self, value):
    if not isinstance(value, list):
      return self.__element_pred(value)

    if self.__is_universal:
      return self.__apply_universal(value)
    else:
      return self.__apply_existential(value)
