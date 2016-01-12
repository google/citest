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

"""Support module for locating JSON objects that have certain field values."""

from . import binary_predicate
from . import lookup_predicate as lookup
from . import path_predicate_result
from . import predicate
from . import quantification_predicate2


class PathPredicate(predicate.ValuePredicate):
  """Delegates value reachable at field path to another predicate.

  Attributes
    path: A '/'-delimited string specifying the path through the object.
    pred: A delegate predicate.ValuePredicate used to find acceptable values.
  """
  @property
  def path(self):
    return self._path

  @property
  def pred(self):
    return self._pred

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(entity, 'Path', self._path)
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self._pred)

  def __init__(self, path, pred=None):
    """Construct finder instance.
    Args:
      path: The path to the field that we would like to find.
      pred: The predicate.ValuePredicate to apply to the field we find.
         This can be None indicating to just find the value at the field.
    """
    self._pred = pred
    self._path = path

  def __eq__(self, finder):
    return (self.__class__ == finder.__class__
            and self._path == finder._path
            and self._pred == finder._pred)

  def __str__(self):
    return '"{path}" {pred}'.format(path=self._path, pred=self._pred)

  def __call__(self, source):
    """Attempt to lookup the field in a JSON object.
    Args:
      source: JSON object to lookup within.

    Returns:
      PredicateResult on the bound predicate applied to the lookup path.
        (i.e. pred(lookup(source, path)))
      If the lookup itself failed, the failed lookup result will be returned.
    """
    lookup_result = (lookup.lookup_path(source, self._path)
                     if self._path
                     else path_predicate_result.JsonFoundValueResult(source))

    if not self._pred or not lookup_result:
      return lookup_result

    pred_result = self._pred(lookup_result.value)
    if isinstance(pred_result, path_predicate_result.JsonPathResult):
      return pred_result.clone_in_context(
          source, path=lookup_result.path, path_trace=lookup_result.path_trace)

    return path_predicate_result.WrappedPathResult(
        valid=pred_result.valid,
        source=source,
        path=lookup_result.path,
        path_trace=lookup_result.path_trace,
        result=pred_result)


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
        path, quantification_predicate2.EXISTS_CONTAINS(operand))
