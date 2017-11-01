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

# pylint: disable=missing-docstring
# pylint: disable=redefined-builtin

import logging

from citest.json_predicate import (
    CardinalityPredicate,
    PathPredicate,
    ValuePredicate,
    AND,
    CONTAINS,
    EQUIVALENT,
    DICT_MATCHES,
    LIST_MATCHES)

from . import observation_predicate as op
from . import observation_verifier as ov
from . import observation_failure as of


class ValueObservationVerifierBuilder(ov.ObservationVerifierBuilder):
  """Builds ValueObservationVerifier instances.

  As a rule of thumb, the path-oriented predicates (e.g. contains_path_*)
  take varargs that include an 'enumerate_terminals' boolean keyword argument
  that specifies whether the predicate should be applied to individual list
  elements or the list itself when the path refers to a list.

  As a rule of thumb, the match-orientd predicates (e.g. contains_*match)
  take varargs that include an 'match_kwargs' dictionary keyword argument
  that propagate the match_kwargs value (if any) to the implied match
  predicate being specified.
  """

  def __init__(self, title, strict=False):
    """Constructor.

    Args:
      title: [string] The name of the verifier for reporting purposes.
      strict: [bool] Whether the verifier is strict or not.
         Strict verifiers require all the objects to satisfy all the
         constraints.  Non-strict verifiers require all the constraints
         to be satisfied by at least one object (but not necessarily the same),
         and some objects may not satisfy any constraints at all.
    """
    super(ValueObservationVerifierBuilder, self).__init__(title)
    self.__strict = strict

  def __eq__(self, builder):
    """Specializes interface."""
    # pylint: disable=protected-access
    return (super(ValueObservationVerifierBuilder, self).__eq__(builder)
            and self.__strict == builder.__strict)

  def _do_build_generate(self, dnf_verifiers):
    """Constructs the actual instance."""
    return ov.ObservationVerifier(
        title=self.title,
        dnf_verifiers=dnf_verifiers)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Strict', self.__strict)
    super(ValueObservationVerifierBuilder, self).export_to_json_snapshot(
        snapshot, entity)

  def add_constraint(self, constraint):
    if not isinstance(constraint, ValuePredicate):
      raise TypeError('{0} is not ValuePredicate'.format(
          constraint.__class__))
    if not (isinstance(constraint, ov.ObservationVerifier)
            or isinstance(constraint, op.ObservationPredicate)):
      constraint = op.ObservationValuePredicate(constraint)
    self.AND(constraint)
    return self

  def contains_path_match(self, path, match_spec, min=1, max=None,
                          **kwargs):
    match_kwargs = kwargs.pop('match_kwargs', {})
    if isinstance(match_spec, list):
      enumerate_terminals = kwargs.pop('enumerate_terminals', False)
      return self.contains_path_pred(
          path, LIST_MATCHES(match_spec, **match_kwargs),
          min, max,
          enumerate_terminals=enumerate_terminals, **kwargs)
    elif isinstance(match_spec, dict):
      return self.contains_path_pred(
          path, DICT_MATCHES(match_spec, **match_kwargs),
          min, max, **kwargs)
    else:
      raise ValueError('match_spec must be a dict or list, not a {0}'
                       .format(match_spec.__class__.__name__))

  def contains_path_value(self, path, value, min=1, max=None, **kwargs):
    return self.contains_path_pred(
        path, CONTAINS(value), min, max, **kwargs)

  def contains_path_eq(self, path, value, min=1, max=None, **kwargs):
    return self.contains_path_pred(
        path, EQUIVALENT(value), min, max, **kwargs)

  def contains_path_pred(self, path, pred, min=1, max=None, **kwargs):
    enumerate_terminals = kwargs.pop('enumerate_terminals', True)
    self.add_constraint(
        CardinalityPredicate(
            PathPredicate(
                path, pred, enumerate_terminals=enumerate_terminals),
            min=min, max=max))
    return self

  def contains_pred_list(self, pred_list, min=1, max=None):
    conjunction = AND(pred_list)
    self.add_constraint(
        CardinalityPredicate(
            conjunction, min=min, max=max))
    return self

  def contains_match(self, match_spec, min=1, max=None, **kwargs):
    match_kwargs = kwargs.pop('match_kwargs', {})
    if isinstance(match_spec, list):
      enumerate_terminals = kwargs.pop('enumerate_terminals', False)
      constraint = LIST_MATCHES(match_spec, **match_kwargs)
      self.add_constraint(
          CardinalityPredicate(
              PathPredicate(
                  '', constraint, enumerate_terminals=enumerate_terminals),
              min=min, max=max,
              **kwargs))
    elif isinstance(match_spec, dict):
      self.add_constraint(
          CardinalityPredicate(
              DICT_MATCHES(match_spec, **match_kwargs),
              min=min, max=max,
              **kwargs))
    else:
      raise ValueError('match_spec must be a dict or list, not a {0}'
                       .format(match_spec.__class__.__name__))

    return self

  def excludes_path_pred(self, path, pred, max=0, **kwargs):
    enumerate_terminals = kwargs.pop('enumerate_terminals', True)
    self.add_constraint(
        CardinalityPredicate(
            PathPredicate(
                path, pred, enumerate_terminals=enumerate_terminals),
            min=0, max=max))
    return self

  def excludes_path_match(self, path, match_spec, max=0, **kwargs):
    match_kwargs = kwargs.pop('match_kwargs', {})
    if isinstance(match_spec, list):
      enumerate_terminals = kwargs.pop('enumerate_terminals', False)
      return self.excludes_path_pred(
          path, LIST_MATCHES(match_spec, **match_kwargs), max,
          enumerate_terminals=enumerate_terminals, **kwargs)
    elif isinstance(match_spec, dict):
      return self.excludes_path_pred(
          path, DICT_MATCHES(match_spec, **match_kwargs), max,
          **kwargs)
    else:
      raise ValueError('match_spec must be a dict or list, not a {0}'
                       .format(match_spec.__class__.__name__))

  def excludes_path_value(self, path, value, max=0):
    return self.excludes_path_pred(path, CONTAINS(value),
                                   max)

  def excludes_path_eq(self, path, value, max=0):
    return self.excludes_path_pred(
        path, EQUIVALENT(value), max)

  def excludes_match(self, match_spec, max=0, **kwargs):
    match_kwargs = kwargs.pop('match_kwargs', {})
    if isinstance(match_spec, list):
      enumerate_terminals = kwargs.pop('enumerate_terminals', False)
      constraint = LIST_MATCHES(match_spec, **match_kwargs)
      self.add_constraint(
          CardinalityPredicate(
              PathPredicate(
                  '', constraint, enumerate_terminals=enumerate_terminals),
              min=0, max=max))
    elif isinstance(match_spec, dict):
      self.add_constraint(
          CardinalityPredicate(
              DICT_MATCHES(match_spec, **match_kwargs),
              min=0, max=max))
    else:
      raise ValueError('match_spec must be a dict or list, not a {0}'
                       .format(match_spec.__class__.__name__))

    return self

  def excludes_pred_list(self, pred_list, max=0):
    conjunction = AND(pred_list)
    self.add_constraint(
        CardinalityPredicate(
            conjunction, min=0, max=max))
    return self
