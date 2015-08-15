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
    return self._path

  @property
  def path_trace(self):
    return self._path_trace

  @property
  def source(self):
    return self._source

  def _make_scribe_parts(self, scribe):
    parts = [scribe.build_part('Path', self._path,
                               relation=scribe.part_builder.CONTROL),
             scribe.part_builder.build_input_part('Source', self._source),
             scribe.part_builder.build_output_part('Trace', self._path_trace)]

    inherited = super(JsonPathResult, self)._make_scribe_parts(scribe)
    return parts + inherited

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
      old_source = self._source or self._value
      path_trace = [path_module.PathValue(path, old_source)]
    else:
      path_trace = path_trace or []

    return self._do_clone_in_context(
        source, self._add_outer_path(path), path_trace + self._path_trace)

  def _do_clone_in_context(self, source, final_path, final_path_trace):
    return self.__class__(
        source=source, path=final_path,
        valid=self.valid, comment=self.comment, cause=self.cause,
        path_trace=final_path_trace)

  def __init__(self, source, path, valid,
               comment=None, pred=None, cause=None, path_trace=None):
    super(JsonPathResult, self).__init__(valid, comment=comment, cause=cause)
    self._source = source
    self._path = path
    self._path_trace = path_trace or []

  def __eq__(self, result):
    return (super(JsonPathResult, self).__eq__(result)
            and self._path == result._path
            and self._source == result._source
            and self._path_trace == result._path_trace)

  def _add_outer_path(self, path):
    """Helper function to add outer context to our path when cloning it."""
    if not path:
      return self._path
    if not self._path:
      return path
    return '{0}/{1}'.format(path, self._path)


class JsonFoundValueResult(JsonPathResult):
  """Predicate result indicating that we found a value.

  Attributes:
    value: The value we found is a JSON compatible type.
    pred: The ValuePredicate used to find the value.
  """

  @property
  def value(self):
    return self._value

  @property
  def pred(self):
    return self._pred

  def _make_scribe_parts(self, scribe):
    parts = [scribe.build_part('Predicate', self._pred,
                               relation=scribe.part_builder.MECHANISM),
             scribe.build_part('Value', self._value,
                               relation=scribe.part_builder.INPUT)]

    inherited = super(JsonFoundValueResult, self)._make_scribe_parts(scribe)
    return parts + inherited

  def _do_clone_in_context(self, source, final_path, final_path_trace):
    return self.__class__(
        value=self._value,
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
     self._pred = pred
     self._value = value

  def __eq__(self, result):
    return (super(JsonFoundValueResult, self).__eq__(result)
             and self._pred == result._pred
             and self._value == result._value)

  def __str__(self):
     parts = ['value={0} pred={1}'.format(self._value, self._pred)]
     if self.path:
       parts.append('source={0!r} path={1!r}'.format(self.source, self.path))
     parts.extend(['trace={0!r}'.format(self.path_trace)])

     parts.append('GOOD' if self._valid else 'BAD')
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

  def _do_clone_in_context(self, source, final_path, final_path_trace):
    return self.__class__(
        expect_type=self._expect_type, got_type=self._got_type,
        source=source, path=final_path, valid=self.valid,
        comment=self.comment, cause=self.cause,
        path_trace=final_path_trace)

  def __init__(self, expect_type, got_type, source, path=None,
               valid=False, comment=None, cause=None, path_trace=None):
      super(JsonTypeMismatchResult, self).__init__(
          source, path, valid, comment=comment, path_trace=path_trace)
      self._expect_type = expect_type
      self._got_type = got_type

  def __str__(self):
    return '{0} is not a {1} for field="{2}" trace={3}.'.format(
      self._got_type, self._expect_type, self.path, self.path_trace)

  def __eq__(self, error):
      return (super(JsonTypeMismatchResult, self).__eq__(error)
              and self._got_type == error._got_type
              and self._expect_type == error._expect_type)


class WrappedPathResult(JsonPathResult):
  def __init__(self, valid, result, source, path, path_trace=None):
    super(WrappedPathResult, self).__init__(
        valid=valid, source=source, path=path, path_trace=path_trace)
    self._result = result

  def __eq__(self, result):
    return (super(WrappedPathResult, self).__eq__(result)
            and self._result == result._result)

  def __str__(self):
    parts = ['path={0!r}'.format(self.path)]
    if self.path_trace:
       parts.extend(['trace={0!r}'.format(self.path_trace)])
    parts.extend([' delegate={0!r}'.format(self._result)])
    return ' '.join(parts)
