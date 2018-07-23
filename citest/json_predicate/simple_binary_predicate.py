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

"""Specialized binary predicates for simple/atomic types."""

import logging
import re
import sys

from .base_binary_predicate import (
    BinaryPredicate)

from .path_value import PathValue

from .path_result import (
    PathValueResult,
    TypeMismatchError)

if sys.version_info[0] > 2:
  basestring = str
  long = int


class SimpleBinaryPredicate(BinaryPredicate):
  """A BinaryPredicate using a bool predicate bound at construction."""

  def __init__(self, name, comparison_op, operand, **kwargs):
    """Constructor.

    Args:
      name: Name of predicate
      comparison_op: Implements bool predicate
      operand: Value to bind to predicate.

      See base class (BinaryPredicate) for additional kwargs.
    """
    super(SimpleBinaryPredicate, self).__init__(name, operand, **kwargs)
    self.__comparison_op = comparison_op

  def __call__(self, context, value):
    operand = self.eval_context_operand(context)
    if self.operand_type and not isinstance(value, self.operand_type):
      return TypeMismatchError(self.operand_type, value.__class__, value)

    valid = self.__comparison_op(value, operand)
    return PathValueResult(pred=self, source=value, target_path='',
                           path_value=PathValue('', value), valid=valid)


class SimpleBinaryPredicateFactory(object):
  """Create a SimpleBinaryPredicate once we have an operand to bind to it."""
  # pylint: disable=too-few-public-methods

  @property
  def predicate_name(self):
    """The name of the predicate for reporting purposes."""
    return self.__name

  def __init__(self, name, comparison_op, **kwargs):
    """Constructor.

    Args:
      name: Name of the comparison_op
      comparison_op: Callable that takes (value, operand) and returns bool.
      operand_type: Class expected for operands, or None to not enforce.
    """
    self.__name = name
    self.__comparison_op = comparison_op
    self.__kwargs = dict(kwargs)

  def __call__(self, operand):
    return SimpleBinaryPredicate(
        self.__name, self.__comparison_op, operand, **self.__kwargs)


DICT_EQ = SimpleBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=dict)
DICT_NE = SimpleBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=dict)

LIST_EQ = SimpleBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=list)
LIST_NE = SimpleBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=list)

NUM_LE = SimpleBinaryPredicateFactory(
    '<=', lambda a, b: a <= b, operand_type=(int, long, float))
NUM_GE = SimpleBinaryPredicateFactory(
    '>=', lambda a, b: a >= b, operand_type=(int, long, float))
NUM_EQ = SimpleBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=(int, long, float))
NUM_NE = SimpleBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=(int, long, float))

STR_SUBSTR = SimpleBinaryPredicateFactory(
    'has-substring', lambda a, b: a.find(b) >= 0, operand_type=basestring)
STR_EQ = SimpleBinaryPredicateFactory(
    '==', lambda a, b: a == b, operand_type=basestring)
STR_NE = SimpleBinaryPredicateFactory(
    '!=', lambda a, b: a != b, operand_type=basestring)

STR_REGEX = SimpleBinaryPredicateFactory(
    'RegEx', lambda a, b: re.search(b, a) != None, operand_type=basestring)


class StandardBinaryPredicate(SimpleBinaryPredicate):
  """DEPRECATED: See SimpleBinaryPredicate."""

  __WARNED = False
  def __init__(self, *posargs, **kwargs):
    if not StandardBinaryPredicate.__WARNED:
      logging.warn(
          'Using DEPRECATED StandardBinaryPredicate instead of SimpleBinaryPredicate')
      __WARNED = True
    super(StandardBinaryPredicate, self).__init__(*posargs, **kwargs)


class StandardBinaryPredicateFactory(SimpleBinaryPredicateFactory):
  """DEPRECATED: See SimpleBinaryPredicateFactory."""

  __WARNED = False
  def __init__(self, *posargs, **kwargs):
    if not StandardBinaryPredicateFactory.__WARNED:
      logging.warn(
          'Using DEPRECATED StandardBinaryPredicateFactory instead of SimpleBinaryPredicateFactory')
      __WARNED = True
    super(StandardBinaryPredicateFactory, self).__init__(*posargs, **kwargs)


