# Copyright 2017 Google Inc. All Rights Reserved.
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

"""Support for matching Exceptions.

Exceptions should not appear in json documents since they are not json.
However other uses of value predicates sometimes want to handle exceptions
using similar infrastructure to ValuePredicate, etc. This is for those
use cases.
"""


import re
from .predicate import (
    ValuePredicate,
    PredicateResult)


class ExceptionMatchesPredicate(ValuePredicate):
  """A predicate that checks a Python exception."""

  @property
  def klass(self):
    """The expected exception class.

    This might be a tuple indicating multiple class options.
    """
    return self.__klass

  @property
  def klass_text(self):
    """A string representation of the class name.

    This accomodates tuples.
    """
    names = []
    all = self.__klass if isinstance(self.__klass, tuple) else [self.__klass]
    for klass in all:
      names.append(klass.__name__)
    return '|'.join(names)

  @property
  def regex(self):
    """An optional regex to expect in the exception message."""
    return self.__regex

  def __init__(self, klass, regex=None):
    self.__klass = klass
    self.__regex = regex

  def __str__(self):
    return '{0}({1})'.format(
        self.klass_text, self.__regex or '.*')

  def __repr__(self):
    return 'class={0}, regex={1}'.format(
        self.klass_text, self.__regex)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__regex == pred.regex)

  def __call__(self, context, value):
    """Implements ValuePredicate interface."""
    value_class_name = value.__class__.__name__
    if not isinstance(value, self.__klass):
      return PredicateResult(
          False,
          comment='Expected {0}, got {1}.'.format(
              self.klass_text, value_class_name))

    if self.__regex:
      regex = context.eval(self.__regex)
      args = value.args
      if len(args) == 1:
        msg = str(args[0])
      else:
        msg = str(args)

      if re.search(regex, msg):
        return PredicateResult(True, comment='Error matches.')
      else:
        return PredicateResult(False, comment='Errors differ.')
    return PredicateResult(True, comment='Error matches.')

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(
        entity, 'Class', self.klass_text)
    if self.__regex:
      snapshot.edge_builder.make_control(
          entity, 'Regex', self.__regex)
