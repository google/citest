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


class ConjunctivePredicate(predicate.ValuePredicate):
  """A ValuePredicate that calls a sequence of predicates until one fails."""

  @property
  def predicates(self):
    return self._conjunction

  def __init__(self, conjunction):
    self._conjunction = [] + conjunction # Elements are ValuePredicate

  def append(self, pred):
    self._conjunction.append(pred)

  def __str__(self):
    return ' AND '.join([str(c) for c in self._conjunction])

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self._conjunction == pred._conjunction)

  def _make_scribe_parts(self, scribe):
    parts = []
    for operand in self._conjunction:
      if not parts:
        parts.append(scribe.build_part('', operand))
      else:
        parts.append(scribe.build_part('AND', operand))
    return parts

  def __call__(self, value):
    all = []
    valid = True
    for pred in self._conjunction:
      result = pred(value)
      all.append(result)
      if not result:
        valid = False
        break;
    return predicate.CompositePredicateResult(
        valid=valid, pred=self, results=all)


class DisjunctivePredicate(predicate.ValuePredicate):
  """A ValuePredicate that calls a sequence of predicates until one succeeds."""

  @property
  def predicates(self):
    return self._disjunction

  def __init__(self, disjunction):
    self._disjunction = [] + disjunction # Elements are ValuePredicate

  def __str__(self):
    return ' OR '.join([str(c) for c in self._disjunction])

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self._disjunction == pred._disjunction)

  def append(self, pred):
    self._disjunction.append(pred)

  def _make_scribe_parts(self, scribe):
    parts = []
    for operand in self._disjunction:
      if not parts:
        parts.append(scribe.build_part('', operand))
      else:
         parts.append(scribe.build_part('OR', operand))
    return parts

  def __call__(self, value):
    all = []
    valid = False
    for pred in self._disjunction:
      result = pred(value)
      all.append(result)
      if result:
        valid = True
        break;
    return predicate.CompositePredicateResult(
        valid=valid, pred=self, results=all)


class NegationPredicate(predicate.ValuePredicate):
  """A ValuePredicate that negates another predicate."""

  @property
  def predicate(self):
    return self._pred

  def __init__(self, predicate):
    self._pred = predicate

  def __str__(self):
    return 'NOT ({0})'.format(self._pred)

  def __eq__(self, other):
    return (self.__class__ == other.__class__
            and self._pred == other._pred)

  def _make_scribe_parts(self, scribe):
    return [scribe.part_builder.build_mechanism_part('Predicate', self._pred)]

  def __call__(self, value):
    base_result = self._pred(value)
    return predicate.CompositePredicateResult(
       valid=not base_result.valid, pred=self, results=[base_result])


class ConditionalPredicate(predicate.ValuePredicate):
  """A ValuePredicate that implements IF/THEN.

  A conditional has an optional ELSE clause.
  If the else clause is provided then the IF condition is evaluated
  then either the THEN or ELSE condition depending on whether the IF was valid
  or not. The final validity is the result of that second (THEN or ELSE)
  result.

  If the ELSE clause is not provided, then the condition evaluates as
  NOT IF or THEN  (transforming the expression using demorgan's law).
  """

  @property
  def if_predicate(self):
    return self._if_pred

  @property
  def then_predicate(self):
    return self._then_pred

  @property
  def else_predicate(self):
    return self._then_pred

  def __init__(self, if_predicate, then_predicate, else_predicate=None):
    """Constructs an if/then clause.

    Args:
      if_predicate: The ValuePredicate acting as the antecedent
      then_predicate: The ValuePredicate acting as the consequent
    """
    self._if_pred = if_predicate
    self._then_pred = then_predicate
    self._else_pred = else_predicate
    self._demorgan_pred = None # If else is none, this is impl as Demogans Law.

    if not else_predicate:
      # The clause is implemented using DeMorgan's law.
      self._demorgan_pred = DisjunctivePredicate(
          [NegationPredicate(if_predicate), then_predicate])

  def __str__(self):
    return 'IF ({0}) THEN ({1})'.format(self._if_pred, self._then_pred)

  def __eq__(self, other):
    return (self.__class__ == other.__class__
            and self._if_pred == other._if_pred
            and self._then_pred == other._then_pred)

  def _make_scribe_parts(self, scribe):
    return [scribe.part_builder.build_mechanism_part('If', self._if_pred),
            scribe.part_builder.build_mechanism_part('Then', self._then_pred)]

  def __call__(self, value):
    if self._demorgan_pred:
      return self._demorgan_pred(value)

    # Run the "if" predicate
    # then, depending on the result, run either "then" or "else" predicate.
    result = self._if_pred(value)
    tried = [result]
    if result:
      result = self._then_pred(value)
    else:
      result = self._else_pred(value)
    tried.append(result)

    return predicate.CompositePredicateResult(
       valid=result.valid, pred=self, results=tried)


AND = ConjunctivePredicate
OR = DisjunctivePredicate
NOT = NegationPredicate
IF = ConditionalPredicate
