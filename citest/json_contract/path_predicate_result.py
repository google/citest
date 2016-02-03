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

from . import path as path_module
from . import predicate


class JsonPathResult(predicate.PredicateResult):
  """Common base class for results whose subject is a field within a composite.

  Attributes:
    path: A '/'-delimited path from the |source| to the field.
    source: The outermost containing object that the |path| is relative to.
    path_trace: The sequence of intermediate objects as the path is traversed
      from the source.
  """

  @property
  def path(self):
    return self.__path

  @property
  def path_trace(self):
    return self.__path_trace

  @property
  def source(self):
    return self.__source

  def export_to_json_snapshot(self, snapshot, entity):
    builder = snapshot.edge_builder
    builder.make_control(entity, 'Path', self.__path)
    builder.make_input(entity, 'Source', self.__source, format='json')
    builder.make_output(entity, 'Trace', self.__path_trace)
    super(JsonPathResult, self).export_to_json_snapshot(snapshot, entity)

  def clone_in_context(self, source, path=None, path_trace=None):
    """Clone this instance, but treat the context as source/path instead.

    Args:
      source: The JSON object that |path| starts in.
      path: The path to the start of our path, or None to keep ours as is.
      path_trace: The path_trace to the start of our path, or None.

    Returns:
      A new instance of our class, but with source=|source|
          and path=|path|+our path.
    """
    if path and not path_trace:
      old_source = self.__source
      path_trace = [path_module.PathValue(path, old_source)]
    else:
      path_trace = path_trace or []

    return self._do_clone_in_context(
        source, self._add_outer_path(path), path_trace + self.__path_trace)

  def _do_clone_in_context(self, source, final_path, final_path_trace):
    return self.__class__(
        source=source, path=final_path,
        valid=self.valid, comment=self.comment, cause=self.cause,
        path_trace=final_path_trace)

  def __init__(self, source, path, valid,
               comment=None, cause=None, path_trace=None):
    super(JsonPathResult, self).__init__(valid, comment=comment, cause=cause)
    self.__source = source
    self.__path = path
    self.__path_trace = path_trace or []

  def __eq__(self, result):
    return (super(JsonPathResult, self).__eq__(result)
            and self.__path == result.__path
            and self.__source == result.__source
            and self.__path_trace == result.__path_trace)

  def _add_outer_path(self, path):
    """Helper function to add outer context to our path when cloning it."""
    if not path:
      return self.__path
    if not self.__path:
      return path
    return '{0}/{1}'.format(path, self.__path)


class JsonFoundValueResult(JsonPathResult):
  """Predicate result indicating that we found a value.

  Attributes:
    value: The value we found is a JSON compatible type.
    pred: The ValuePredicate used to find the value.
  """

  @property
  def value(self):
    return self.__value

  @property
  def pred(self):
    return self.__pred

  def export_to_json_snapshot(self, snapshot, entity):
    snapshot.edge_builder.make_mechanism(entity, 'Predicate', self.__pred)
    snapshot.edge_builder.make_input(entity, 'Value', self.__value,
                                     format='json')
    super(JsonFoundValueResult, self).export_to_json_snapshot(snapshot, entity)

  def _do_clone_in_context(self, source, final_path, final_path_trace):
    return self.__class__(
        value=self.__value,
        source=source, path=final_path, valid=self.valid,
        comment=self.comment, pred=self.pred, cause=self.cause,
        path_trace=final_path_trace)

  def __init__(self, value,
               source=None, path=None, valid=True,
               comment=None, pred=None, cause=None, path_trace=None):
    if source == None:
      source = value
    if not path_trace and path:
      path_trace = [path_module.PathValue(path, source)]

    super(JsonFoundValueResult, self).__init__(
        source, path, valid,
        comment=comment, cause=cause, path_trace=path_trace)
    self.__pred = pred
    self.__value = value

  def __eq__(self, result):
    return (super(JsonFoundValueResult, self).__eq__(result)
            and self.__pred == result.pred
            and self.__value == result.value)

  def __str__(self):
    parts = ['value={0} pred={1}'.format(self.__value, self.__pred)]
    if self.path:
      parts.append('source={0!r} path={1!r}'.format(self.source, self.path))
      parts.extend(['trace={0!r}'.format(self.path_trace)])

    parts.append('GOOD' if self.valid else 'BAD')
    return ' '.join(parts)


class JsonMissingPathResult(JsonPathResult):
  """A PredicatePathResult indicating the desired path did not exist."""

  def __init__(self, source, path, valid=False, comment=None, cause=None,
               path_trace=None):
    super(JsonMissingPathResult, self).__init__(
        source=source, path=path, valid=valid, comment=comment, cause=cause,
        path_trace=path_trace)


class JsonTypeMismatchResult(JsonPathResult):
  """A PredicatePathResult indicating the field was not the expected type."""

  @property
  def expect_type(self):
    return self.__expect_type

  @property
  def got_type(self):
    return self.__got_type

  def _do_clone_in_context(self, source, final_path, final_path_trace):
    return self.__class__(
        expect_type=self.__expect_type, got_type=self.__got_type,
        source=source, path=final_path, valid=self.valid,
        comment=self.comment, cause=self.cause,
        path_trace=final_path_trace)

  def __init__(self, expect_type, got_type, source, path=None,
               valid=False, comment=None, cause=None, path_trace=None):
    super(JsonTypeMismatchResult, self).__init__(
        source, path, valid, comment=comment, path_trace=path_trace)
    self.__expect_type = expect_type
    self.__got_type = got_type

  def __str__(self):
    return '{0} is not a {1} for field="{2}" trace={3}.'.format(
        self.__got_type, self.__expect_type, self.path, self.path_trace)

  def __eq__(self, error):
    return (super(JsonTypeMismatchResult, self).__eq__(error)
            and self.__got_type == error.got_type
            and self.__expect_type == error.expect_type)


class WrappedPathResult(JsonPathResult):
  @property
  def result(self):
    return self.__result

  def __init__(self, valid, result, source, path, path_trace=None):
    super(WrappedPathResult, self).__init__(
        valid=valid, source=source, path=path, path_trace=path_trace)
    self.__result = result

  def __eq__(self, result):
    return (super(WrappedPathResult, self).__eq__(result)
            and self.__result == result.result)

  def __str__(self):
    parts = ['path={0!r}'.format(self.path)]
    if self.path_trace:
      parts.extend(['trace={0!r}'.format(self.path_trace)])
    parts.extend([' delegate={0!r}'.format(self.__result)])
    return ' '.join(parts)
