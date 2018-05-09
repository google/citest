# Copyright 2018 Google Inc. All Rights Reserved.
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

"""HTTP Response Predicates."""


import re
import citest.json_predicate as jp

from . import HttpResponseType


class HttpResponsePredicateResult(jp.PredicateResult):
  """Result from an HttpResponsePredicate."""

  @property
  def value(self):
    """The value the predicate was applied to."""
    return self.__value

  def __init__(self, valid, value, **kwargs):
    super(HttpResponsePredicateResult, self).__init__(valid, **kwargs)
    self.__value = value

  def __eq__(self, result):
    return (super(HttpResponsePredicateResult, self).__eq__(result)
            and self.__value == result.value)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    builder.make_output(entity, 'HTTP Code', self.__value.http_code)
    if self.__value.output:
      builder.make_output(entity, 'HTTP Payload', self.__value.output)
    super(HttpResponsePredicateResult, self).export_to_json_snapshot(snapshot,
                                                                     entity)

class HttpResponsePredicate(jp.ValuePredicate):
  """Determine if an object matches an expected HttpResponse."""

  @property
  def http_code(self):
    """The expected HTTP code or None."""
    return self.__http_code

  @property
  def content_regex(self):
    """Describes the expected response content or None."""
    return self.__content_regex

  def __init__(self, http_code=None, content_regex=None, **kwargs):
    """Constructor.

    Args:
      http_code: [int] The expected http_code or None.
      content_regex: [string] A regex for the expected content None.

      See base class (ValuePredicate) for additional kwargs.
    """
    if http_code is None and content_regex is None:
      raise ValueError('Needs at least an http_code or content_regex.')

    self.__http_code = http_code
    self.__content_regex = content_regex
    super(HttpResponsePredicate, self).__init__(**kwargs)

  def __call__(self, context, value):
    if not isinstance(value, HttpResponseType):
      return jp.PredicateResult(
          valid=False,
          comment='{0} != HttpType'.format(value.__class__.__name__))

    message = ['HttpResponse']
    sep = 'with'  # Separator between confirmation phrases.
    if self.__http_code is not None:
      if self.__http_code != value.http_code:
        return HttpResponsePredicateResult(
            False, value,
            comment='HTTP Status={0} != {1}'.format(value.http_code,
                                                    self.__http_code))

      message.append('{0} HTTP Status={1}'.format(sep, self.__http_code))
      sep = 'and'

    if self.__content_regex is not None:
      if not re.search(self.__content_regex, value.output):
        return HttpResponsePredicateResult(
            False, value,
            comment='Response content does not match "{0}"'.format(
                self.__content_regex))

      message.append('{0} content matches "{1}"'.format(
          sep, self.__content_regex))

    return HttpResponsePredicateResult(True, value, comment=' '.join(message))

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
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
