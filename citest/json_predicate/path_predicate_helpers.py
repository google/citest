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

"""Additional helper utilities based on PathPredicate for common usage."""

from .path_predicate import PathPredicate
from . import binary_predicate


class PathEqPredicate(PathPredicate):
  """Specialization of PathPredicate that forces '==' predicate."""
  def __init__(self, path, operand):
    super(PathEqPredicate, self).__init__(
        path, binary_predicate.EQUIVALENT(operand))


class PathContainsPredicate(PathPredicate):
  """Specialization of PathPredicate that forces 'contains' predicate.

  The contains predicate depends on the values being compared:
      value type | predicate
      -----------+--------------
      string     | is substring
      dict       | is subset
      list       | if operand is a list, is subset, else is element
      other      | is equal
  """
  def __init__(self, path, operand):
    super(PathContainsPredicate, self).__init__(
        path, binary_predicate.CONTAINS(operand))


class PathElementsContainPredicate(PathPredicate):
  """Specialization of PathPredicate that forces EXISTS_CONTAINS predicate."""
  def __init__(self, path, operand):
    super(PathElementsContainPredicate, self).__init__(
        path, binary_predicate.CONTAINS(operand))
