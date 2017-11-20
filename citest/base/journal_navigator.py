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
import os

try:
  from StringIO import StringIO
except ImportError:
  from io import StringIO

from .record_stream import RecordInputStream


class JournalNavigator(object):
  """Iterates over journal JSON."""

  @property
  def journal_id(self):
    """Returns identifier specifying original location of content."""
    raise NotImplementedError('{0}.journal_id not implemented'.format(
        self.__class__.__name__))

  @property
  def journal_name(self):
    """Provides the name of the journal, typically the file basename."""
    raise NotImplementedError('{0}.journal_name not implemented'.format(
        self.__class__.__name__))

  def next(self):
    """Return the next item in the journal.

    Raises:
      StopIteration when there are no more elements.
    """
    raise NotImplementedError('{0}.next() not implemented'.format(
        self.__class__.__name__))


class StreamJournalNavigator(JournalNavigator):
  """Iterates over journal JSON from a stream."""

  def __next__(self):
    return self.next()

  def open(self, path):
    """Open the journal to be able to iterate over its contents.

    Args:
      path: [string] The path to load the journal from.
    """
    if self.__input_stream is not None:
      raise ValueError('Navigator is already open.')
    self.__input_stream = RecordInputStream(open(path, 'rb'))

  @staticmethod
  def new_from_path(path):
    """Create a new navigator using the contents of a file.

    Args:
      path: [string] Path to journal file.
    """
    with open(path, 'rb') as stream:
      return StreamJournalNavigator.new_from_bytes(path, stream.read())

  @staticmethod
  def new_from_bytes(journal_id, contents):
    """Create a new navigator using the given record-encoded journal.

    Args:
      journal_id: [string] Identifies the source of the bytes.
      contents: [string] Raw byte contents of a record-encoded journal file.
    """
    return StreamJournalNavigator(
        journal_id, RecordInputStream(StringIO(contents)))

  @property
  def journal_id(self):
    return self.__id

  @property
  def journal_name(self):
    basename = os.path.basename(self.__id)
    if basename.endswith('.journal'):
      basename = os.path.splitext(basename)[0]
    return basename

  def __init__(self, journal_id, stream):
    """Constructor"""
    self.__id = journal_id
    self.__input_stream = stream
    self.__decoder = json.JSONDecoder()

  def __iter__(self):
    return self

  def next(self):
    """Return the next item in the journal.

    Raises:
      StopIteration when there are no more elements.
    """
    json_str = next(self.__input_stream)

    try:
      return self.__decoder.decode(json_str)

    except ValueError:
      logging.error('Invalid json record:\n%s', json_str)
      raise
