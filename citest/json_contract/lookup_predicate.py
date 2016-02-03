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


"""Support module for walking JSON objects.

Lookup functions populate PredicateResult objects rather than just returning
values, so are heavier weight than would be otherwise. In return they provide
traceability on how matches were made, or why they could not be made.
"""


from . import path_predicate_result as jc
from . import path as path_module


def _lookup_path_elements(list_obj, path):
  """Lookup a path value in a member of a JSON list object.

  This is a helper function for lookup_path_in_list().

  Args:
    list_obj: A JSON list object to iterate over until an element is found.
    path: A '/'-delimited path specifying the path to the value we want
      rooted at the list elements.

  Returns:
    PredicateResult containing the error or a valid PredicateFoundValueResult
    with the value.
  """
  for elem in list_obj:
    result = lookup_path(elem, path)
    if result:
      return result

  return jc.JsonMissingPathResult(list_obj, path)


def lookup_path(source, path):
  """Lookup the value of a field within a JSON object.

  Args:
    source: The JSON object to look within.
        If it is a list, then iterate over its elements.
    path: A slash-delimited string denoting the fields to traverse.
        If a list value is encountered within the traversal then
        the elements in the list will be iterated over as the traversal
        continues, giving each element a shot.

  Returns:
    A valid PredicateFoundValueResult or an invalid PredicateResult if path
    is not reachable.
  """
  value = source
  path_trace = []
  path_offset = 0
  while path_offset < len(path):
      # pylint: disable=bad-indentation
      if isinstance(value, list):
        result = _lookup_path_elements(value, path[path_offset:])
        if path_offset > 0:
          result = result.clone_in_context(
              source=source, path=path[path_offset - 1:], path_trace=path_trace)
        else:
          result = result.clone_in_context(source=source)

        return result

      if not isinstance(value, dict):
          return jc.JsonTypeMismatchResult(
              source=source, path=path[0:path_offset],
              expect_type=dict, got_type=value.__class__)

      slash = path.find('/', path_offset)
      if slash < 0:
        field = path[path_offset:]
        path_offset = len(path)
      elif slash == 0:
        raise ValueError('path cannot be absolute')
      else:
        field = path[path_offset:slash]
        path_offset = slash + 1

      try:
        value = value[field]
        path_trace.append(path_module.PathValue(field, value))
      except KeyError:
        return jc.JsonMissingPathResult(value, field, path_trace=path_trace)

  return jc.JsonFoundValueResult(
      source=source, value=value, path=path, path_trace=path_trace)
