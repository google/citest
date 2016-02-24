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


"""Implements a Journal for managing JSON snapshots to a file.

The JSON snspahosts in a journal are JsonSnashot. A journal is a collection
of snapshots and, in future, other events.
"""

import json
import threading
import time

from .record_stream import RecordOutputStream
from .snapshot import JsonSnapshot

class Journal(object):
  """Stores object snapshots into an output file.

  The output file will contain a binary stream containing each journal entry
  as a 32-bit framed json document. That is there will be a 32-bit length
  (in network byte order) followed by a JSON string containing the entry.
  The frame length is the json string length. This gives the journal some
  resiliency to premature crashes and invalid json encodings of individual
  entries.

  The journal is thread-safe so multiple threads can write into it
  concurrently.
  """

  def __init__(self, now_function=time.time):
    """Constructs new journal.

    Args:
      now_function: [time] Optional override for timestamping function.
          Returns a real value indicating the current time.
    """
    self.__encoder = json.JSONEncoder(indent=2, separators=(',', ': '))
    self.__lock = threading.Lock()
    self.__now_function = now_function
    self.__output = None

  def now(self):
    """Returns current timestamp for marking journal entries."""
    return self.__now_function()

  def open_with_path(self, _path, **metadata):
    """Start a new journal file at the given path.

    Args:
      _path: [string] Path to file to write into.
      metadata: [kwargs] Metadata for initial entry.
    """
    self.open_with_file(open(_path, 'r'), **metadata)

  def open_with_file(self, _output, **metadata):
    """
    Args:
      output: [FileObject] Takes ownership of the file to store snapshots into.
      metadata: [kwargs] Metadata for initial message.
    """
    self.__lock.acquire(True)
    try:
      if self.__output is not None:
        raise ValueError('Journal is already open.')

      self.__output = RecordOutputStream(_output)
    finally:
      self.__lock.release()

    self.write_message('Starting journal.', **metadata)

  def terminate(self, **metadata):
    """Stops writing into journal.

    Args:
      metadata: [kwargs]  Defines final metadata entry summarizing the journal.
    """
    self.write_message('Finished journal.', **metadata)
    self.__lock.acquire(True)
    try:
      if self.__output is None:
        raise ValueError('Journal is already terminated.')
      self._do_close()
      self.__output = None
    finally:
      self.__lock.release()

  def begin_context(self, _title, **metadata):
    """Write a begin context marker into the journal.

    Args:
      _title: [string] Title for the context.
      metadata: [kwargs] Additional metadata for the entry.
    """
    entry = {
        '_type': 'JournalContextControl',
        'control': 'BEGIN',
        '_title': _title
    }
    entry.update(metadata)
    self.__write_json_object(entry)

  def end_context(self, **metadata):
    """Write a end context marker into the journal.

    Args:
      metadata: [kwargs] Additional metadata for the entry.
    """
    entry = {
        '_type': 'JournalContextControl',
        'control': 'END',
    }
    entry.update(metadata)
    self.__write_json_object(entry)

  def write_message(self, _text, **metadata):
    """Write a message into the journal.

    Args:
      _text: [string] The message text to write.
      metadata: [kwargs] Additional metadata for the entry.
    """
    if not isinstance(_text, basestring) and _text is not None:
      raise TypeError('{0} is not basestring'.format(_text.__class__))

    entry = {
        '_type': 'JournalMessage',
        '_value': _text,
    }
    entry.update(metadata)
    self.__write_json_object(entry)

  def store(self, obj, **metadata):
    """Stores an object as a graph within the journal.

    Args:
      obj: [JsonSnapshotable] The object to store into the journal.
      metadata: [kwargs] Additional metadata for the entry.
    """
    snapshot = JsonSnapshot(**metadata)
    snapshot.add_data(obj)
    self.__write_json_object(snapshot.to_json_object())

  def _do_close(self):
    """Actually closes the journal output file.

    This is a hook for testing before we lose the output file.
    """
    self.__output.close()

  def __write_json_object(self, json_object):
    """Write JSON object into the journal file.

    Args:
      json_object: [any] Encodable object to store into the snapshot
    """

    json_copy = dict(json_object)
    json_copy.setdefault('_timestamp', self.now())
    json_copy.setdefault('_thread', threading.current_thread().ident)

    # protect both the encoder and the output stream.
    self.__lock.acquire(True)
    try:
      if self.__output is None:
        raise ValueError('Journal is not open')

      text = self.__encoder.encode(json_copy)
      self.__output.append(text)
    finally:
      self.__lock.release()
