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
import unittest
from StringIO import StringIO
from citest.base import Journal
from citest.base import (JsonSnapshot, JsonSnapshotable)


class TestDetails(JsonSnapshotable):
  def export_to_json_snapshot(self, snapshot, entity):
    snapshot.edge_builder.make(entity, 'DetailR', 3.14)
    snapshot.edge_builder.make(entity, 'DetailB', True)


class TestData(JsonSnapshotable):
  def __init__(self, name, param, data=None):
    self.__name = name
    self.__param = param
    self.__data = data

  def export_to_json_snapshot(self, snapshot, entity):
    entity.add_metadata('name', self.__name)
    entity.add_metadata('param', self.__param)

    if self.__data:
      data = snapshot.make_entity_for_data(self.__data)
      snapshot.edge_builder.make(entity, 'Data', data)
    return entity


class TestClock(object):
  _BASE_TIME = 100.123
  @property
  def last_time(self):
    return self.next_time - 1

  @property
  def elapsed_time(self):
    return self.next_time - TestClock._BASE_TIME

  def __init__(self):
    self.next_time = TestClock._BASE_TIME

  def __call__(self):
    self.next_time += 1
    return self.last_time


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
        '_timestamp': _clock.last_time
    }
    if metadata_dict:
      entry.update(metadata_dict)
    return json.JSONEncoder(indent=2, separators=(',', ': ')).encode(entry)

  def test_empty(self):
    """Verify the journal starts end ends with the correct JSON text."""

    output = StringIO()
    journal = TestJournal(output)
    initial_json_text = self.expect_message_text(journal.clock,
                                                 'Starting journal.')
    self.assertEquals('[{0}'.format(initial_json_text),
                      output.getvalue())

    journal.terminate()
    final_json_text = self.expect_message_text(journal.clock,
                                               'Finished journal.')
    self.assertEquals('[{0},\n{1}]'.format(initial_json_text, final_json_text),
                      journal.final_content)

  def test_write_plain_message(self):
    """Verify the journal contains messages we write into it."""
    output = StringIO()
    journal = TestJournal(output)
    initial_json_text = self.expect_message_text(journal.clock,
                                                 'Starting journal.')
    self.assertEquals('[{0}'.format(initial_json_text),
                      output.getvalue())

    offset = len(output.getvalue())
    journal.write_message('A simple message.')
    message_json_text = self.expect_message_text(journal.clock,
                                                 'A simple message.')
    self.assertEquals(',\n' + message_json_text, output.getvalue()[offset:])

    offset = len(output.getvalue())
    journal.terminate()
    final_json_text = self.expect_message_text(journal.clock,
                                               'Finished journal.')
    self.assertEquals(',\n' + final_json_text,
                      journal.final_content[offset:-1])

  def test_write_message_with_metadata(self):
    """Verify the journal messages contain the metadata we add."""
    output = StringIO()
    journal = TestJournal(output)
    offset = len(output.getvalue())

    journal.write_message('My message.', str='ABC', num=123)
    metadata = {'str': 'ABC', 'num': 123}
    message_json_text = self.expect_message_text(
        journal.clock, 'My message.', metadata)

    decoder = json.JSONDecoder(encoding='ASCII')
    self.assertItemsEqual(decoder.decode(message_json_text),
                          decoder.decode(output.getvalue()[offset + 2:]))

  def test_store(self):
    """Verify we store objects as JSON snapshots."""
    data = TestData('NAME', 1234, TestDetails())
    decoder = json.JSONDecoder(encoding='ASCII')
    snapshot = JsonSnapshot()
    snapshot.add_data(data)

    time_function = lambda: 1.23
    journal = Journal(time_function)
    output = StringIO()
    journal.open_with_file(output)
    offset = len(output.getvalue())

    journal.store(data)
    contents = output.getvalue()
    got = decoder.decode(contents[offset + 2:])  # skip ',\n'
    json_object = snapshot.to_json_object()
    json_object['_timestamp'] = time_function()
    self.assertItemsEqual(json_object, got)

  def test_lifecycle(self):
    """Verify we store multiple objects as a list of snapshots."""
    first = TestData('first', 1, TestDetails())
    second = TestData('second', 2)

    journal = TestJournal(StringIO())

    journal.store(first)
    journal.store(second)
    journal.terminate()

    decoder = json.JSONDecoder(encoding='ASCII')
    got = decoder.decode(journal.final_content)
    self.assertEquals(4, len(got))

    snapshot = JsonSnapshot()
    snapshot.add_data(first)
    json_object = snapshot.to_json_object()
    json_object['_timestamp'] = journal.clock.last_time - 1
    self.assertItemsEqual(json_object, got[1])

    snapshot = JsonSnapshot()
    snapshot.add_data(second)
    json_object = snapshot.to_json_object()
    json_object['_timestamp'] = journal.clock.last_time
    self.assertItemsEqual(json_object, got[2])


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JournalTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
