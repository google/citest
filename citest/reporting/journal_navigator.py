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

from citest.base import RecordInputStream


class JournalNavigator(object):
  """Iterates over journal JSON."""

  def __init__(self):
    """Constructor"""
    self.__input_stream = None
    self.__decoder = json.JSONDecoder()

  def __iter__(self):
    """Iterate over the contents of the journal."""
    self.__check_open()
    return self

  def open(self, path):
    """Open the journal to be able to iterate over its contents.

    Args:
      path: [string] The path to load the journal from.
    """
    if self.__input_stream != None:
      raise ValueError('Navigator is already open.')
    self.__input_stream = RecordInputStream(open(path, 'r'))

  def close(self):
    """Close the journal."""
    self.__check_open()
    self.__input_stream.close()
    self.__input_stream = None

  def next(self):
    """Return the next item in the journal.

    Raises:
      StopIteration when there are no more elements.
    """
    self.__check_open()
    json_str = next(self.__input_stream)

    try:
      return self.__decoder.decode(json_str)

    except ValueError:
      print 'Invalid json record:\n{0}'.format(json_str)
      raise

  def __check_open(self):
    """Verify that the navigator is open (and thus valid to iterate)."""
    if self.__input_stream is None:
      raise ValueError('Navigator is not open.')
