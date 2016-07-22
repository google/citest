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

"""Helper functions for verifying errors against Google API Clients."""


import re

from googleapiclient.errors import HttpError

from .. import json_contract as jc
from .. import json_predicate as jp


class HttpErrorPredicateResult(jp.PredicateResult):
  """Result from an HttpErrorPredicate."""

  @property
  def value(self):
    """The value the predicate was applied to."""
    return self.__value

  def __init__(self, valid, value, comment=None):
    super(HttpErrorPredicateResult, self).__init__(valid, comment=comment)
    self.__value = value

  def __eq__(self, result):
    return (super(HttpErrorPredicateResult, self).__eq__(result)
            and self.__value == result.value)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    builder.make_output(entity, 'Error Value', self.__value)
    super(HttpErrorPredicateResult, self).export_to_json_snapshot(snapshot,
                                                                  entity)

class HttpErrorPredicate(jp.ValuePredicate):
  """Determine if an object matches an expected HttpError."""

  @property
  def http_code(self):
    """The expected HTTP code or None."""
    return self.__http_code

  @property
  def content_regex(self):
    """Describes the expected response content or None."""
    return self.__content_regex

  def __init__(self, http_code=None, content_regex=None):
    """Constructor.

    Args:
      http_code: [int] The expected http_code or None.
      content_regex: [string] A regex for the expected content None.
    """
    if http_code is None and content_regex is None:
      raise ValueError('Needs at least an http_code or content_regex.')

    self.__http_code = http_code
    self.__content_regex = content_regex

  def __call__(self, value):
    if not isinstance(value, HttpError):
      return jp.PredicateResult(
          valid=False,
          comment='{0} != HttpType'.format(value.__class__.__name__))

    message = ['HttpError']
    sep = 'with'  # Separator between confirmation phrases.
    if self.__http_code is not None:
      if self.__http_code != value.resp.status:
        return HttpErrorPredicateResult(
            False, value,
            comment='HTTP Status={0} != {1}'.format(value.resp.status,
                                                    self.__http_code))

      message.append('{0} HTTP Status={1}'.format(sep, self.__http_code))
      sep = 'and'

    if self.__content_regex is not None:
      if not re.search(self.__content_regex, value.content):
        return HttpErrorPredicateResult(
            False, value,
            comment='Response content does not match "{0}"'.format(
                self.__content_regex))

      message.append('{0} content matches "{1}"'.format(
          sep, self.__content_regex))

    return HttpErrorPredicateResult(True, value, comment=' '.join(message))

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    if self.__http_code:
      snapshot.edge_builder.make_control(entity, 'HTTP Code', self.__http_code)
    if self.__content_regex:
      snapshot.edge_builder.make_control(entity, 'Regex',
                                         self.__content_regex)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__http_code == pred.http_code
            and self.__content_regex == pred.content_regex)

  def __str__(self):
    parts = []
    if self.__http_code is not None:
      parts.append('http_code={0}'.format(self.__http_code))
    if self.__content_regex is not None:
      parts.append('contains={0}'.format(self.__content_regex))
    return ', '.join(parts)


class GoogleAgentObservationFailureVerifier(jc.ObservationVerifier):
  """An ObservationVerifier that expects specific errors from stderr."""

  def __init__(self, title, http_code=None, content_regex=None):
    """Constructs the clause with the acceptable status and/or error regex.

    Args:
      title: Verifier name for reporting purposes only.
      http_code: [int] The specific HTTP status code that is expected or None.
      content_regex: [string] Regex pattern expected in error response content
          or None.
    """
    super(GoogleAgentObservationFailureVerifier, self).__init__(title)
    self.__pred = HttpErrorPredicate(http_code, content_regex)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(entity, 'Expect', self.__pred)
    super(GoogleAgentObservationFailureVerifier, self).export_to_json_snapshot(
        snapshot, entity)

  def __call__(self, observation):
    """Check if observation contains the expected HTTP error.

    Args:
      observation: [Observation] The observation
    """
    good_results = []
    bad_results = []

    if not observation.errors:
      bad_results.append(jp.PredicateResult(
          False, comment='No errors observed.'))

    for error in observation.errors:
      result = self.__pred(error)
      if result:
        good_results.append(result)
      else:
        bad_results.append(result)

    if good_results:
      failed_constraints = []
      comment = 'Observed expected error.'
    else:
      failed_constraints = [self.__pred]
      comment = 'Did not observe expected error.'

    return jc.ObservationVerifyResult(
        valid=good_results != [], observation=observation,
        good_results=good_results, bad_results=bad_results,
        failed_constraints=failed_constraints, comment=comment)
