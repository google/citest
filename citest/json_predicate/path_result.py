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


"""Implements core PredicateResult specializations when operating on paths."""
# pylint: disable=too-many-arguments


from .path_value import (
    PATH_SEP,
    PathValue)

from .predicate import (
    CloneableWithContext,
    PredicateResult)


class PathResult(PredicateResult, CloneableWithContext):
  """Common base class for results whose subject is a field within a composite.

  Attributes:
    target_path: A '/'-delimited path from the |source| to the desired field.
    source: The outermost containing object that the |path| is relative to.
    path_value: An actual path value.
  """

  @property
  def target_path(self):
    """The desired path."""
    return self.__target_path

  @property
  def path_value(self):
    """The PathValue that we found, or None.

    This might not have the full target_path, but will be a subset.
    """
    return self.__path_value

  @property
  def source(self):
    """The source JSON object that we are extracting the path from."""
    return self.__source

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    builder.make_control(entity, 'Target Path', self.__target_path)
    builder.make_input(entity, 'Source', self.__source, format='json')
    builder.make_output(entity, 'PathValue', self.__path_value)
    super(PathResult, self).export_to_json_snapshot(snapshot, entity)

  def clone_in_context(self, source, base_target_path, base_value_path):
    """Implements CloneableWithContext interface."""
    target_path = (base_target_path if not self.__target_path
                   else PATH_SEP.join([base_target_path, self.__target_path]))
    value_path = (base_value_path if not self.__path_value.path
                  else PATH_SEP.join([base_target_path,
                                      self.__path_value.path]))
    path_value = PathValue(value_path, self.__path_value.value)

    return self._do_clone_in_context(source, target_path, path_value)

  def _do_clone_in_context(self, source, final_path, final_path_value):
    return self.__class__(
        source=source, target_path=final_path, path_value=final_path_value,
        valid=self.valid, comment=self.comment, cause=self.cause)

  def __init__(self, valid, source, target_path, path_value,
               comment=None, cause=None):
    super(PathResult, self).__init__(valid, comment=comment, cause=cause)
    self.__source = source
    self.__target_path = target_path
    self.__path_value = (PathValue(target_path, source)
                         if path_value is None else path_value)

  def __eq__(self, result):
    return (super(PathResult, self).__eq__(result)
            and self.__target_path == result.target_path
            and self.__source == result.source
            and self.__path_value == result.path_value)

  def __add_outer_path(self, base_path):
    """Helper function to add outer context to our path when cloning it."""
    if not base_path:
      return self.__target_path
    if not self.__target_path:
      return base_path
    return '{0}/{1}'.format(base_path, self.__target_path)

  def __repr__(self):
    """Specializes interface."""
    return '{4} source={0} target_path={1} path_value={2} valid={3}'.format(
        self.source, self.target_path, self.path_value, self.valid,
        self.__class__.__name__)


class PathValueResult(PathResult):
  """A PathResult referencing a particular value."""

  @property
  def pred(self):
    """The predicate used to filter the value, if any."""
    return self.__pred

  def __init__(self, source, target_path, path_value, valid=False, pred=None,
               comment=None, cause=None):
    # pylint: disable=redefined-builtin
    """Constructor.

    Args:
      source: [obj] The original JSON object path_value is relative to.
         This can be none if the path_value is the root path.
      target_path: [string] The desired path (relative to source) that
         we were looking for. NOTE: This is probably path_value.path.
      path_value: [PathValue] The path value the filter was applied to.
      pred: [ValuePredicate] The predicate applied as the filter, if any.
      valid: [bool] Whether the PredicateResult indicates success.
      comment: [string] Optional comment for reporting.
      cause: [Error or PredicateResult] Optional for reporting.
    """
    super(PathValueResult, self).__init__(
        source=source, target_path=target_path, path_value=path_value,
        valid=valid, comment=comment, cause=cause)
    self.__pred = pred

  def __eq__(self, result):
    return (super(PathValueResult, self).__eq__(result)
            and self.__pred == result.pred)

  def __repr__(self):
    """Specializes interface."""
    return '{0} pred={1}'.format(super(PathValueResult, self).__repr__(),
                                 self.__pred)

  def _do_clone_in_context(self, source, final_path, final_path_value):
    """Specializes interface to pass through filter."""
    return self.__class__(
        source=source, target_path=final_path, path_value=final_path_value,
        valid=self.valid, pred=self.__pred,
        comment=self.comment, cause=self.cause)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    if self.__pred:
      builder.make_control(entity, 'Filter', self.__pred)
    super(PathValueResult, self).export_to_json_snapshot(snapshot, entity)


class MissingPathError(PathResult):
  """A PathResult indicating the desired path did not exist."""

  def __init__(self, source, target_path, path_value=None,
               valid=False, comment=None, cause=None):
    """Constructor.

    Args:
      source: [obj] The original JSON object path_value is relative to.
         This can be none if the path_value is the root path.
      target_path: [string] The desired path (relative to source) that
         we were looking for. NOTE: This is probably path_value.path.
      path_value: [PathValue] The path value as far along as we could go.
      valid: [bool] Whether the PredicateResult indicates success.
      comment: [string] Optional comment for reporting.
      cause: [Error or PredicateResult] Optional for reporting.
    """
    super(MissingPathError, self).__init__(
        valid=valid, source=source, target_path=target_path,
        path_value=path_value, comment=comment, cause=cause)


class TypeMismatchError(PathResult):
  """A PathResult indicating the field was not the expected type."""

  @property
  def expect_type(self):
    """The type we expected."""
    return self.__expect_type

  @property
  def got_type(self):
    """The value type we found."""
    return self.__got_type

  def _do_clone_in_context(self, source, final_path, final_path_value):
    """Specializes interface to pass through types."""

    return self.__class__(
        expect_type=self.__expect_type, got_type=self.__got_type,
        source=source, target_path=final_path, path_value=final_path_value,
        valid=self.valid,
        comment=self.comment, cause=self.cause)

  def __init__(self, expect_type, got_type,
               source, target_path=None, path_value=None,
               valid=False, comment=None, cause=None):
    """Constructor.

    Args:
      expect_type: [type] The type we wanted.
      got_type: [type] The type we actually found.
      source: [obj] The original JSON object path_value is relative to.
         This can be none if the path_value is the root path.
      target_path: [string] The desired path (relative to source) that
         we were looking for. NOTE: This is probably path_value.path.
      path_value: [PathValue] The path value as far along as we could go.
      valid: [bool] Whether the PredicateResult indicates success.
      comment: [string] Optional comment for reporting.
      cause: [Error or PredicateResult] Optional for reporting.
    """
    super(TypeMismatchError, self).__init__(
        valid=valid, source=source, target_path=target_path,
        path_value=path_value, comment=comment, cause=cause)
    self.__expect_type = expect_type
    self.__got_type = got_type

  def __str__(self):
    """Specializes interface."""
    return '{0} is not a {1} for field="{2}" trace={3}.'.format(
        self.__got_type, self.__expect_type, self.target_path, self.path_value)

  def __repr__(self):
    """Specializes interface."""
    return (super(TypeMismatchError, self).__repr__()
            + ' expect_type={0} got_type={1}'.format(
                self.expect_type, self.got_type))

  def __eq__(self, error):
    """Specializes interface."""
    return (super(TypeMismatchError, self).__eq__(error)
            and self.__got_type == error.got_type
            and self.__expect_type == error.expect_type)


class IndexBoundsError(PathResult):
  """A PathResult indicating an array index out of bounds."""

  @property
  def index(self):
    """The index we asked for."""
    return self.__index

  def __init__(self, index, source, target_path, path_value,
               valid=False, comment=None, cause=None):
    """Constructor.

    Args:
      index: [int] The index we attempted to access.
      source: [obj] The original JSON object path_value is relative to.
         This can be none if the path_value is the root path.
      target_path: [string] The desired path (relative to source) that
         we were looking for.
      path_value: [PathValue] The path value we attempted to index into.
      valid: [bool] Whether the PredicateResult indicates success.
      comment: [string] Optional comment for reporting.
      cause: [Error or PredicateResult] Optional for reporting.
    """
    super(IndexBoundsError, self).__init__(
        valid=valid, source=source, target_path=target_path,
        path_value=path_value, comment=comment)
    if not isinstance(path_value.value, list):
      raise TypeError('{0} is not a list', path_value.value.__class__)
    self.__index = index
    self.__max = len(path_value.value)

  def __str__(self):
    """Specializes interface."""
    return '{0} is not in the range 0..{1} for path_value={2}.'.format(
        self.__index, self.__max, self.path_value)

  def __eq__(self, error):
    """Specializes interface."""
    return (super(IndexBoundsError, self).__eq__(error)
            and self.__index == error.index)
