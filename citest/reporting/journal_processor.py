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


"""Processes a journal by calling specialized handlers on each entry."""

from .journal_navigator import JournalNavigator


class ProcessedEntityManager(object):
  """Helper class to help processing handlers keep track of where we are.

  This is used to manage the nesting and references of entities within
  the snapshot graphs.

  It maintains a stack of the Entity id's that we are processing in order to
  detect cycles. It maintains a mapping of id's to entities in order to resolve
  linked relationships among entities.
  """

  @property
  def ids_in_progress(self):
    """The navigation path we took to get to the current ID being processed."""
    return self.__id_stack

  def __init__(self):
    """Constructor."""
    self.__map_stack = []
    self.__id_stack = []

  def lookup_entity_with_id(self, entity_id):
    """Find the referenced JsonSnapshot journal entity.

    Args:
      entity_id: [int] The identifier being referenced.

    Returns:
      The loaded JSON object denoting the referenced entity.

    Raises:
      KeyError if the entity_id is not known.
      This would indicate an invalid JSON journal.
    """
    str_id = str(entity_id)

    # We are only checking the top element here because snapshots should be
    # encapsulated. Needing to look deeper in the stack suggests that the local
    # snapshot isnt encapsulated. It might turn out that snapshots should be
    # composable in the future, but currently they are not.
    found = (self.__map_stack[-1].get(str_id)
             or self.__map_stack[-1].get(entity_id))
    if not found:
      raise KeyError('No entity for {0} in {1} of {2}'.format(
          entity_id, self.__map_stack[-1], len(self.__map_stack)))
    return found

  def push_entity_map(self, entity_map):
    """Add a map of entities for future lookup.

    Args:
      entity_map: [map of int to JSON entity]
    """
    self.__map_stack.append(entity_map)

  def pop_entity_map(self, expect_map):
    """Pop the most recent entity map.

    Args:
      entity_map: The map we expect to pop.
    Raises:
      ValueError if the stack isnt what we expected.
    """
    got = self.__map_stack.pop()
    if id(got) != id(expect_map):
      raise ValueError(
          'Entity stack out of whack: got={0} expected={1}'.format(
              got, expect_map))

  def begin_id(self, entity_id):
    """Push entity_id into our processing stack."""
    self.__id_stack.append(entity_id)

  def end_id(self, expect_id):
    """Pop entity_id from our processing stack.

    Raises:
       ValueError if our stack is not as expected.
    """
    got = self.__id_stack.pop()
    if got != expect_id:
      raise ValueError(
          'Entity stack out of whack: got={0} expected={1}'.format(
              got, expect_id))


class JournalProcessor(object):
  """Processes a journal by calling specialized handlers on each entry.

  Maintains a registry of specialized handlers keyed by the '_type' of entry.
  The handlers are injected from the outside.
  """
  @property
  def handler_registry(self):
    """Registry of callable objects, keyed by "_type", taking the JSON obj."""
    return self.__handler_registry

  @property
  def default_handler(self):
    """The default handler when an unregistered "_type" is encountered."""
    return self.__default_handler

  @default_handler.setter
  def default_handler(self, handler):
    """Sets the default handler.

    Args:
      handler: [None (obj)] where obj is the JSON object in the journal.
    """
    self.__default_handler = handler if handler else self.handle_unknown

  def __init__(self, registry=None):
    """Constructor.

    Args:
      registry: [dict] Keyed by string matching the "_type" attribute in the
         journal object read. The values are callable objects that take the
         decoded JSON object from the journal. Return values are ignored.
    """
    self.__handler_registry = dict(registry or {})
    self.__default_handler = self.handle_unknown

  def process(self, input_path):
    """Process the contents of the journal indicatd by input_path.

    Args:
      input_path: [string] The path to the journal.
    """
    navigator = JournalNavigator()
    navigator.open(input_path)
    try:
      for obj in navigator:
        entry_type = obj.get('_type')
        handler = (self.__handler_registry.get(entry_type)
                   or self.__default_handler)
        handler(obj)

    finally:
      navigator.close()

  def handle_unknown(self, obj):
    """The default handler for processing entries with unregistered _type.

    Args:
      obj: [dict] The decoded json journal entry will contain a '_type'
          identifying it.
    """
    entry_type = obj.get('_type')
    raise ValueError('Unknown journal entry type: {0}:\n{1}'.format(
        entry_type, obj))
