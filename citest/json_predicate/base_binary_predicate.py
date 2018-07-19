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

"""Binary predicates define a predicate relating the value to a fixed operand.

For example a comparator operation that compares a given value against a
reference point. The reference point would be the fixed operand, and the given
value would be the value that the base interface is given to apply the
predicate to.
"""

import inspect
from .predicate import ValuePredicate


class BinaryPredicate(ValuePredicate):
  """
  The base class for standard binary predicates.

  All the BinaryPredicates are constructed with an operand, which is the
  "operand" in the binary operator that you want to compare against.
  The other of operands is passed into the "__call__" method as a specific
  "value" to run the predicate against.

  For example, a predicate that checks for numbers < 10 would be constructed
  with an operand of 10: pred = INT_LT(10)
  Then to test a particular value, such as 5, you would pass 5 into the call
  operator (along with an evaluation context): result = pred(context, 5)

  Note that the operand bound into the predicate can itself be a callable if
  the desired wont be known until later. In this case, the callable will be
  invoked with an execution context which, presumably, will be populated using
  a pre-negotiated key (e.g. hardcoded) with the actual value to use.
     pred = INT_LT(lambda context: context['MyKey'])
     context['MyKey'] = 10
     result = pred(context, 5)

  Attributes:
    name: The name of the predicate is used to specify the particular
        comparison predicate to use. The supported names are:
    operand: The operand to compare against. This is the RHS of the predicate.
  """
  # pylint: disable=abstract-method

  @property
  def name(self):
    """The predicate name."""
    return self.__name

  @property
  def operand(self):
    """The fixed operand argument."""
    return self.__operand

  @property
  def operand_type(self):
    """The expected type of the operand."""
    return self.__operand_type

  def eval_context_operand(self, context):
    """Determine the operand type for the given evaluation context."""
    operand = context.eval(self.__operand)
    if self.__operand_type and not isinstance(operand, self.__operand_type):
      raise TypeError(
          '{0} is not {1}: {2!r}',
          operand.__class__, self.__operand_type, operand)
    return operand

  def __str__(self):
    if self.__operand_type is None:
      type_name = 'Any'
    elif inspect.isclass(self.__operand_type):
      type_name = self.__operand_type.__name__
    else:
      type_name = str(self.__operand_type)
    return '{0}({1!r})->{2}'.format(self.name, self.operand, type_name)

  def __init__(self, name, operand, **kwargs):
    self.__operand_type = kwargs.pop('operand_type', None)
    self.__name = name
    self.__operand = operand
    if self.__operand_type is not None and not callable(self.__operand):
      if not isinstance(self.__operand, self.__operand_type):
        raise TypeError(
            '{0} "{1}" is not {2}: {3!r}'.format(
                operand.__class__, name, self.__operand_type, operand))
    super(BinaryPredicate, self).__init__(**kwargs)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__name == pred.name
            and self.__operand == pred.operand
            and self.__operand_type == pred.operand_type)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make(entity, 'Name', self.__name)
    snapshot.edge_builder.make_control(entity, 'Operand', self.__operand)
