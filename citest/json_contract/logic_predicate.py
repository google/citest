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
