# Copyright 2016 Google Inc. All Rights Reserved.
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

"""Support module for locating JSON objects that have certain field values.

The PathPredicate is the main ValuePredicate for extracting values from JSON
objects based on their paths. This predicate is a wrapper around a function,
collect_path_values, that does most of the work.

Values in the result are always ambiguous because a path can reference a list
of values, or have a list of values as an element within it. Therefore the
predicate always returns lists of objects rather than a single object.

A path is a PATH_SEP-delimited string of legal JSON attribute names,
index specifiers, or attribute_names delimited with an index specifier.
An index specifier is a string '[<number>]' where <number> are the digits
of the 0-based index of a particular list element.

For example, consider the source {'a': [{'x': 'X',
                                         'y': [1, 2, 3, {'z':'Z'}, {'z':4}]},
                                        'Plain']}
   Path         Values
   ----         ------
   ''           {'a': [{'x': 'X', 'y': [1, 2, 3, {'z': 'Z'}]}, 'Plain']}
   'a'          {'x':'X', 'y':[1,2,3, {'z':'Z'}, {'z':4}]}
                'Plain'
   'a[0]'       {'x':'X', 'y':[1,2,3, {'z':'Z'}, {'z':4}]}
   'a[1]'       'Plain'
   'a[0]/x'     'X'
   'a[0]/y'     [1,2,3,{'z':'Z'}]
   'a[0]/y[0]'  1
   'a[0]/y[3]'  {'z': 'Z'}
   'a[0]/y/z    ['Z', 4]
   'a/x'        'X'
   'a/y'        [1,2,3, {'z':'Z'}, {'z':4}]
   'a/y/z'      ['Z', 4]
   'a/y/z[0]'   'Z'


The path indicies are not required unless you want to specify a particular
index. Omitting the index will consider all the elements when traversing the
path.

Results returned include the path taken to the object, and the value of the
object. The paths taken in the results are always explicit including the
exact index in the source.
"""


import collections
import re

from .path_value import (
    PATH_SEP,
    PathValue)

from .predicate import (
    CloneableWithContext,
    ValuePredicate)

from .path_predicate_result import PathPredicateResultBuilder

from .path_result import (
    MissingPathError,
    PathValueResult,
    TypeMismatchError,
    IndexBoundsError)


# An internal data structure used to queue path values as we navigate.
_QueueElement = collections.namedtuple('QueueElem',
                                       ['path_offset', 'path_value'])


# Terminal used to mean dont enumerate the value if it is a list
DONT_ENUMERATE_TERMINAL = '@'

# Compiled regex to parse out a path element index specifier if present.
# This strips out the brackets and next slash, if any.
_INDEX_RE = re.compile(r'\{0}?\[(\d+)\]'.format(PATH_SEP))


# Compiled regex to parse out the next path element name.
# This strips out the next slash, if any.
_SEGMENT_RE = re.compile(r'\{0}?([^\{0}\{1}\[]+)'.format(
    PATH_SEP, DONT_ENUMERATE_TERMINAL))


def _process_dict_element(elem, target_path):
  """Helper function for processing dictionary objects in the queue.

  Args:
    elem: [_QueueElement] Element to process has a list value.
    target_path: [string] The desired path we were looking for.

  Returns:
    array of _QueueElement
  """
  path_offset = elem.path_offset
  from_path_value = elem.path_value

  # The value of the path to this point is the end of the trace.
  base_path = from_path_value.path
  source = from_path_value.value

  # Continue tracing from this object to the path remainder.
  # Determine the next path segment we are looking for.
  match = _INDEX_RE.search(target_path, path_offset)
  if match is not None and match.start(0) == path_offset:
    return TypeMismatchError(list, dict, source, target_path, from_path_value)
  match = _SEGMENT_RE.search(target_path, path_offset)
  if match is None:
    next_offset = len(target_path)
    next_segment = target_path[path_offset:]

    if path_offset == next_offset - 1 and next_segment == PATH_SEP:
      # Terminal enumerated dict is just itself.
      return [_QueueElement(next_offset, from_path_value)], []
  else:
    next_offset = match.end(0)
    next_segment = match.groups(0)[0]

  # Add the segment to the path to this value.
  # This is not strictly the path up to the next offset
  # because we might be decorating the path (e.g. array indexes taken).
  if not base_path:
    value_path = next_segment
  else:
    value_path = PATH_SEP.join([base_path, next_segment])

  # Get the segment value, if any.
  value = source.get(next_segment, None)
  if value is None:
    return (
        [],
        [MissingPathError(source, next_segment, path_value=from_path_value)])

  return ([_QueueElement(next_offset, PathValue(value_path, value))], [])


def _process_list_element(elem, target_path):
  """Helper function for processing list objects in the queue.

  Args:
    elem: [_QueueElement] Element to process has a list value.
    target_path: [string] The desired path we were looking for.

  Returns:
    array of _QueueElement
  """
  path_offset = elem.path_offset
  from_path_value = elem.path_value

  # The value of the path to this point is the end of the trace.
  base_path = from_path_value.path
  source = from_path_value.value

  filter_index = None
  match = _INDEX_RE.search(target_path, path_offset)
  if match is not None and match.start(0) == path_offset:
    filter_index = int(match.groups(0)[0])
    if filter_index >= len(source):
      return [], [IndexBoundsError(filter_index, list,
                                   target_path=target_path[path_offset:],
                                   path_value=from_path_value)]

    path_offset = match.end(0)

  # Try to follow the path from each of the objects in the list.
  candidates = []
  fails = []
  for index, value in enumerate(source):
    if filter_index is not None and index != filter_index:
      continue

    elem_path = '{0}[{1}]'.format(base_path, index)
    candidates.append(
        _QueueElement(path_offset, PathValue(elem_path, value)))

  return candidates, fails


def _process_queue_element(top, target_path):
  """Determine all the next values in the given path for the queue element.

  Args:
    top: [_QueueElement] The queue element to process.
    target_path: [string] The original desired path.

  Returns:
    array of _QueueElement
  """

  if isinstance(top.path_value.value, dict):
    return _process_dict_element(top, target_path)

  if isinstance(top.path_value.value, list):
    return _process_list_element(top, target_path)

  source = top.path_value.value
  path_offset = top.path_offset
  if target_path[path_offset] == PATH_SEP:
    path_offset += 1

  return ([],
          [MissingPathError(source, target_path[path_offset:],
                            path_value=top.path_value)])


class ProducesPathPredicateResult(object):
  """Marker indicating ValuePredicate's result implements HasPathPredicateResult

  This is a temporary hack that could be replaced with a class property
  indicating the result class that is returned. See HasPathPredicateResult
  for more info.
  """
  # pylint: disable=too-few-public-methods
  pass


class PathPredicate(ValuePredicate, ProducesPathPredicateResult):
  """Delegates value reachable at field path to another predicate."""

  @property
  def path(self):
    """A PATH_SEP-delimited string specifying the path through the object."""
    return self.__path

  @property
  def pred(self):
    """A delegate ValuePredicate used to find acceptable values."""
    return self.__pred

  @property
  def transform(self):
    """An optional function transforming the source value into a final value."""
    return self.__transform

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(entity, 'Path', self.__path)
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self.__pred)
    if self.__transform:
      snapshot.edge_builder.make_mechanism(
          entity, 'Transform', self.__transform)

  def __init__(self, path, pred=None, transform=None):
    """Construct finder instance.
    Args:
      path: The path to the field that we would like to find.
      pred: The ValuePredicate to apply to the field we find.
         This can be None indicating to just find the value at the field.
      transform: An optional transformation function to apply to the path value.
    """
    self.__pred = pred
    self.__path = path or ''
    self.__transform = transform

  def __eq__(self, finder):
    return (self.__class__ == finder.__class__
            and self.__path == finder.path
            and self.__pred == finder.pred
            and self.__transform == finder.transform)

  def __str__(self):
    xform = '{0} '.format(self.__transform) if self.__transform else ''
    return '"{path}" {xform}{pred}'.format(
        path=self.__path, xform=xform, pred=self.__pred)

  def __call__(self, source):
    """Attempt to lookup the field in a JSON object.
    Args:
      source: JSON object to lookup within.

    Returns:
      PredicateResult on the bound predicate applied to the lookup path.
        (i.e. pred(lookup(source, path)))
    """

    path = self.__path

    builder = PathPredicateResultBuilder(pred=self, source=source)
    enumerate_terminal = True
    if path and path[-1] in (PATH_SEP, DONT_ENUMERATE_TERMINAL):
      enumerate_terminal = path[-1] != DONT_ENUMERATE_TERMINAL
      path = path[:-1]

    queue = [_QueueElement(0, PathValue('', source))]
    if not path and not (enumerate_terminal and isinstance(source, list)):
      return self.__add_queue_to_builder(builder, queue, enumerate_terminal)

    final_queue = []
    while queue:
      top = queue.pop(0)
      if top.path_offset >= len(path):
        final_queue.append(top)
        continue

      candidates, fails = _process_queue_element(top, path)
      queue.extend(candidates)
      builder.add_all_path_failures(fails)

    return self.__add_queue_to_builder(builder, final_queue, enumerate_terminal)

  def __add_queue_to_builder(self, builder, final_queue, enumerate_terminal):
    """Helper method for processing the final candidates from the queue.

    Apply the filter bound to this predicate, if any, to determine whether
    each of the final candidates should be kept or rejected.

    Args:
      builder: [PathPredicateResultBuilder] To add the results into.
      final_queue: [list of _QueueElement] The final candidate values.
      enumerate_terminal: [bool] If true, then list values in the queue
         should be enumerated (one level) into individual elements.

    Returns:
      PathPredicateResult
    """
    for elem in final_queue:
      value = elem.path_value.value
      if enumerate_terminal and isinstance(value, list):
        candidates, fails = _process_queue_element(elem, self.__path)
        # We're already at the end point, so there is no more path based
        # filtering to do. The above step would have just expanded out
        # the list elements into individual elements, which should never
        # fail.
        assert len(fails) == 0
      else:
        candidates = [elem]

      if self.__pred is None:
        for trial in candidates:
          if self.__transform:
            xformed = self.__transform(trial.path_value.value)
            transformed_path_value = PathValue(trial.path_value.path, xformed)
          else:
            transformed_path_value = trial.path_value

          builder.add_result_candidate(
              trial.path_value,
              PathValueResult(source=builder.source,
                              target_path=transformed_path_value.path,
                              path_value=transformed_path_value,
                              valid=True,
                              pred=None))

      else:
        for trial in candidates:
          path_value = trial.path_value
          pred_result = self.__pred(path_value.value)
          if isinstance(pred_result, CloneableWithContext):
            base_path = path_value.path
            pred_result = pred_result.clone_in_context(
                source=builder.source,
                base_target_path=self.__path,
                base_value_path=base_path)

          builder.add_result_candidate(path_value, pred_result)

    return builder.build()
