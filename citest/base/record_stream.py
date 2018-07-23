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


"""Implements a frame protocol for writing sized blocks of binary data."""
import struct
import sys

if sys.version_info[0] > 2:
  basestring = str


class RecordOutputStream(object):
  """Writes data elements to framed stream with 32-bit frame lengths."""

  @property
  def stream(self):
    """Returns the delegate stream being written to."""
    return self.__stream

  def __init__(self, stream):
    """Constructor.

    Args:
      stream: [stream] The stream to write into.
    """
    self.__stream = stream

  def close(self):
    """Closes the delegate stream."""
    self.__stream.close()

  def append(self, data):
    """Appends a record to the stream.

    Args:
      data: [string] The string (array of bytes) to write.
    """
    if not isinstance(data, basestring):
      raise TypeError('{0} is not a string'.format(type(data)))
    encoded_data = str.encode(data)
    count = len(encoded_data)
    self.__stream.write(struct.pack('!I', count))
    self.__stream.write(encoded_data)


class RecordInputStream(object):
  """Reads data elements from a framed stream with 32-bit frame lengths."""

  @property
  def stream(self):
    """Returns the delegate stream being written to."""
    return self.__stream

  def __init__(self, stream):
    """Constructor.

    Args:
      stream: [stream] The stream to read from.
    """
    self.__stream = stream

  def __iter__(self):
    """Makes this iterable over the frames."""
    return self

  def __next__(self):
    return self.next()

  def close(self):
    """Closes the delegate stream."""
    self.__stream.close()

  def next(self):
    """Reads the next frame data from the stream.

    Returns:
      The next binary string data written into the stream.

    Raises:
      StopIteration if there are no more records.
      ValueError if the stream is corrupt.
    """
    size = self.__stream.read(4)
    if len(size) == 0:
      raise StopIteration()

    if len(size) != 4:
      raise ValueError('Frame is corrupted len={0} of 4'.format(len(size)))

    count = struct.unpack('!I', size)[0]
    value = self.__stream.read(count)
    if len(value) != count:
      raise ValueError(
          'Frame is corrupted -- missing {0}'.format(count - len(value)))
    return bytes.decode(value)
