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

"""Various journal iterators to facilitate navigating through journal JSON."""

import json


class JournalNavigator(object):
  """Iterates over journal JSON."""

  def __init__(self):
    """Constructor"""
    self.__file = None
    self.__json_doc = None
    self.__doc_len = None
    self.__doc_index = None

  def __iter__(self):
    """Iterate over the contents of the journal."""
    self.__check_open()
    return self

  def __len__(self):
    """Return number of entries in the journal."""
    self.__check_open()
    return self.__doc_len

  def open(self, path):
    """Open the journal to be able to iterate over its contents.

    Args:
      path: [string] The path to load the journal from.
    """
    if self.__file != None:
      raise ValueError('Navigator is already open.')
    self.__file = open(path, 'r')
    self.__json_doc = json.JSONDecoder().decode(self.__file.read())
    self.__doc_index = 0
    self.__doc_len = len(self.__json_doc)

  def close(self):
    """Close the journal."""
    self.__check_open()
    self.__file.close()
    self.__file = None
    self.__json_doc = None

  def next(self):
    """Return the next item in the journal.

    Raises:
      StopIteration when there are no more elements.
    """
    self.__check_open()
    if self.__doc_index >= self.__doc_len:
      raise StopIteration()

    json_obj = self.__json_doc[self.__doc_index]
    self.__doc_index += 1
    return json_obj

  def __check_open(self):
    """Verify that the navigator is open (and thus valid to iterate)."""
    if self.__file == None:
      raise ValueError('Navigator is not open.')
