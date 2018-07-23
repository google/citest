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


"""Test journal module."""
# pylint: disable=missing-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=invalid-name


import json
import threading
import unittest

from io import BytesIO
from citest.base import Journal

from citest.base import JsonSnapshot, JsonSnapshotableEntity
from citest.base import RecordOutputStream, RecordInputStream

from tests.base.test_clock import TestClock


class TestDetails(JsonSnapshotableEntity):
  def export_to_json_snapshot(self, snapshot, entity):
    snapshot.edge_builder.make(entity, 'DetailR', 3.14)
    snapshot.edge_builder.make(entity, 'DetailB', True)


class TestData(JsonSnapshotableEntity):
  def __init__(self, name, param, data=None):
    self.__name = name
    self.__param = param
    self.__data = data

  def export_to_json_snapshot(self, snapshot, entity):
    entity.add_metadata('name', self.__name)
    entity.add_metadata('param', self.__param)

    if self.__data:
      data = snapshot.make_entity_for_object(self.__data)
      snapshot.edge_builder.make(entity, 'Data', data)
    return entity


class TestJournal(Journal):

  @property
  def clock(self):
    return self.__clock

  def __init__(self, output):
    self.__clock = TestClock()
    super(TestJournal, self).__init__(now_function=self.__clock)
    self.open_with_file(output)
    self.__output = output
    self.final_content = None

  def _do_close(self):
    self.final_content = self.__output.getvalue()
    super(TestJournal, self)._do_close()


class JournalTest(unittest.TestCase):

  @staticmethod
  def expect_message_text(_clock, _text, metadata_dict=None):
    entry = {
        '_type': 'JournalMessage',
        '_value': _text,
        '_thread': threading.current_thread().ident,
        '_timestamp': _clock.last_time
    }
    if metadata_dict:
      entry.update(metadata_dict)
    return json.JSONEncoder(indent=2, separators=(',', ': ')).encode(entry)

  def assertMessagesEqual(self, expect, got):
    expect_stream = RecordInputStream(BytesIO(expect))
    got_stream = RecordInputStream(BytesIO(got))
    while True:
      try:
        expect_data = next(expect_stream)
      except StopIteration:
        break
      got_data = next(got_stream)
      self.assertItemsEqual(expect_data, got_data)

    with self.assertRaises(StopIteration):
      next(got_stream)     

  def assertItemsEqual(self, a, b):
    """See if items are equal independent of sort order."""
    self.assertEquals(sorted(a), sorted(b))

  def test_empty(self):
    """Verify the journal starts end ends with the correct JSON text."""

    output = BytesIO()
    journal = TestJournal(output)
    initial_json_text = self.expect_message_text(journal.clock,
                                                 'Starting journal.')
    expect_stream = RecordOutputStream(BytesIO())
    expect_stream.append(initial_json_text)

    self.assertMessagesEqual(expect_stream.stream.getvalue(), output.getvalue())

    journal.terminate()
    final_json_text = self.expect_message_text(journal.clock,
                                               'Finished journal.')
    expect_stream.append(final_json_text)
    self.assertMessagesEqual(expect_stream.stream.getvalue(), journal.final_content)

  def test_write_plain_message(self):
    """Verify the journal contains messages we write into it."""
    output = BytesIO()
    journal = TestJournal(output)
    initial_json_text = self.expect_message_text(journal.clock,
                                                 'Starting journal.')

    expect_stream = RecordOutputStream(BytesIO())
    expect_stream.append(initial_json_text)
    self.assertMessagesEqual(expect_stream.stream.getvalue(), output.getvalue())

    journal.write_message('A simple message.')
    message_json_text = self.expect_message_text(journal.clock,
                                                 'A simple message.')
    expect_stream.append(message_json_text)
    self.assertMessagesEqual(expect_stream.stream.getvalue(), output.getvalue())

    journal.terminate()
    final_json_text = self.expect_message_text(journal.clock,
                                               'Finished journal.')
    expect_stream.append(final_json_text)
    self.assertMessagesEqual(expect_stream.stream.getvalue(), journal.final_content)

  def test_write_message_with_metadata(self):
    """Verify the journal messages contain the metadata we add."""
    output = BytesIO()
    journal = TestJournal(output)
    offset = len(output.getvalue())

    journal.write_message('My message.', str='ABC', num=123)
    metadata = {'str': 'ABC', 'num': 123}
    message_json_text = self.expect_message_text(
        journal.clock, 'My message.', metadata)

    input_stream = RecordInputStream(BytesIO(output.getvalue()[offset:]))
    decoder = json.JSONDecoder()
    expect_obj = decoder.decode(message_json_text)
    got_obj = decoder.decode(next(input_stream))
    self.assertItemsEqual(expect_obj, got_obj)

  def test_store(self):
    """Verify we store objects as JSON snapshots."""
    data = TestData('NAME', 1234, TestDetails())
    decoder = json.JSONDecoder()
    snapshot = JsonSnapshot()
    snapshot.add_object(data)

    time_function = lambda: 1.23
    journal = Journal(time_function)
    output = BytesIO()
    journal.open_with_file(output)
    offset = len(output.getvalue())

    journal.store(data)
    contents = output.getvalue()
    got_stream = RecordInputStream(BytesIO(contents[offset:]))
    got_json_str = next(got_stream)
    got = decoder.decode(got_json_str)
    json_object = snapshot.to_json_object()
    json_object['_timestamp'] = time_function()
    json_object['_thread'] = threading.current_thread().ident
    self.assertItemsEqual(json_object, got)

  def test_lifecycle(self):
    """Verify we store multiple objects as a list of snapshots."""
    first = TestData('first', 1, TestDetails())
    second = TestData('second', 2)

    journal = TestJournal(BytesIO())

    journal.store(first)
    journal.store(second)
    journal.terminate()

    decoder = json.JSONDecoder()
    got_stream = RecordInputStream(BytesIO(journal.final_content))
    got_str = [e for e in got_stream]
    got_json = '[{0}]'.format(','.join(got_str))
    got = decoder.decode(got_json)
    self.assertEquals(4, len(got))

    snapshot = JsonSnapshot()
    snapshot.add_object(first)
    json_object = snapshot.to_json_object()
    json_object['_timestamp'] = journal.clock.last_time - 1
    json_object['_thread'] = threading.current_thread().ident
    self.assertItemsEqual(json_object, got[1])

    snapshot = JsonSnapshot()
    snapshot.add_object(second)
    json_object = snapshot.to_json_object()
    json_object['_timestamp'] = journal.clock.last_time
    json_object['_thread'] = threading.current_thread().ident
    self.assertItemsEqual(json_object, got[2])


if __name__ == '__main__':
  unittest.main()
