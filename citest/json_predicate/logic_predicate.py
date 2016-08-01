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

"""Declares some predicates useful for expressing IF/AND/OR conditions."""


from . import predicate


class ConjunctivePredicate(predicate.ValuePredicate):
  """A ValuePredicate that calls a sequence of predicates until one fails."""

  @property
  def predicates(self):
    """The list of predicates that are ANDed together."""
    return self.__conjunction

  def __init__(self, conjunction):
    self.__conjunction = [] + conjunction # Elements are ValuePredicate

  def append(self, pred):
    """Adds predicate to the conjunction."""
    self.__conjunction.append(pred)

  def __str__(self):
    return ' AND '.join([str(c) for c in self.__conjunction])

  def __repr__(self):
    return ' AND '.join([repr(c) for c in self.__conjunction])

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.predicates == pred.predicates)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make(entity, 'Conjunction', self.__conjunction,
                               join='AND')

  def __call__(self, value):
    everything = []
    valid = True
    for pred in self.__conjunction:
      result = pred(value)
      everything.append(result)
      if not result:
        valid = False
        break
    return predicate.CompositePredicateResult(
        valid=valid, pred=self, results=everything)


class DisjunctivePredicate(predicate.ValuePredicate):
  """A ValuePredicate that calls a sequence of predicates until one succeeds."""

  @property
  def predicates(self):
    """The list of predicates that are ORed together."""
    return self.__disjunction

  def __init__(self, disjunction):
    self.__disjunction = [] + disjunction # Elements are ValuePredicate

  def __str__(self):
    return ' OR '.join([str(c) for c in self.__disjunction])

  def __repr__(self):
    return ' OR '.join([repr(c) for c in self.__disjunction])

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.predicates == pred.predicates)

  def append(self, pred):
    """Adds predicate to the disjunction."""
    self.__disjunction.append(pred)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make(entity, 'Disjunction', self.__disjunction,
                               join='OR')

  def __call__(self, value):
    everything = []
    valid = False
    for pred in self.__disjunction:
      result = pred(value)
      everything.append(result)
      if result:
        valid = True
        break
    return predicate.CompositePredicateResult(
        valid=valid, pred=self, results=everything)


class NegationPredicate(predicate.ValuePredicate):
  """A ValuePredicate that negates another predicate."""

  @property
  def predicate(self):
    """The list of predicates that are NOTed together."""
    return self.__pred

  def __init__(self, pred):
    self.__pred = pred

  def __str__(self):
    return 'NOT ({0})'.format(self.__pred)

  def __repr__(self):
    return 'NOT ({0!r})'.format(self.__pred)

  def __eq__(self, other):
    return (self.__class__ == other.__class__
            and self.__pred == other.predicate)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self.__pred)

  def __call__(self, value):
    base_result = self.__pred(value)
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
    """The predicate forming the IF condition."""
    return self.__if_pred

  @property
  def then_predicate(self):
    """The predicate forming the THEN clause."""
    return self.__then_pred

  @property
  def else_predicate(self):
    """The predicate forming the ELSE clause."""
    return self.__then_pred

  def __init__(self, if_predicate, then_predicate, else_predicate=None):
    """Constructs an if/then clause.

    Args:
      if_predicate: The ValuePredicate acting as the antecedent
      then_predicate: The ValuePredicate acting as the consequent
    """
    self.__if_pred = if_predicate
    self.__then_pred = then_predicate
    self.__else_pred = else_predicate
    self.__demorgan_pred = None # If else is None, this is Demogans Law.

    if not else_predicate:
      # The clause is implemented using DeMorgan's law.
      self.__demorgan_pred = DisjunctivePredicate(
          [NegationPredicate(if_predicate), then_predicate])

  def __str__(self):
    return 'IF ({0}) THEN ({1})'.format(self.__if_pred, self.__then_pred)

  def __repr__(self):
    return 'IF ({0!r}) THEN ({1!r})'.format(self.__if_pred, self.__then_pred)

  def __eq__(self, other):
    return (self.__class__ == other.__class__
            and self.__if_pred == other.if_predicate
            and self.__then_pred == other.then_predicate
            and self.__else_pred == other.else_predicate)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_mechanism(entity, 'If', self.__if_pred)
    snapshot.edge_builder.make_mechanism(entity, 'Then', self.__then_pred)
    if self.__else_pred:
      snapshot.edge_builder.make_mechanism(entity, 'Else', self.__else_pred)

  def __call__(self, value):
    if self.__demorgan_pred:
      return self.__demorgan_pred(value)

    # Run the "if" predicate
    # then, depending on the result, run either "then" or "else" predicate.
    result = self.__if_pred(value)
    tried = [result]
    if result:
      result = self.__then_pred(value)
    else:
      result = self.__else_pred(value)
    tried.append(result)

    return predicate.CompositePredicateResult(
        valid=result.valid, pred=self, results=tried)


AND = ConjunctivePredicate
OR = DisjunctivePredicate
NOT = NegationPredicate
IF = ConditionalPredicate
