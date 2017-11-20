# Copyright 2018 Google Inc. All Rights Reserved.
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

"""Test citest.reporting.html_renderer module."""

import os
import shutil
import tempfile
import unittest

from citest.base import (
    Journal,
    StreamJournalNavigator)


class StreamNavigatorTest(unittest.TestCase):
  # pylint: disable=missing-docstring

  @classmethod
  def setUpClass(cls):
    cls.temp_dir = tempfile.mkdtemp(prefix='journal_nav_test')

  @classmethod
  def tearDownClass(cls):
    shutil.rmtree(cls.temp_dir)

  def test_iterator(self):
    journal = Journal()
    path = os.path.join(self.temp_dir, 'test_iterator.journal')
    expect = []

    journal.open_with_path(path, TestString='TestValue', TestNum=123)
    expect.append({'_type': 'JournalMessage',
                   '_value': 'Starting journal.',
                   'TestString': 'TestValue',
                   'TestNum': 123})

    journal.write_message('Initial Message')
    expect.append({'_type': 'JournalMessage', '_value': 'Initial Message'})
                   
    journal.begin_context('OUTER', TestProperty='BeginOuter')
    expect.append({'_type': 'JournalContextControl',
                   'control': 'BEGIN',
                   '_title': 'OUTER',
                   'TestProperty': 'BeginOuter'})

    journal.write_message('Context Message', format='pre')
    expect.append({'_type': 'JournalMessage', '_value': 'Context Message',
                   'format': 'pre'})
    
    journal.end_context(TestProperty='END OUTER')
    expect.append({'_type': 'JournalContextControl',
                   'control': 'END',
                   'TestProperty': 'END OUTER'})

    journal.terminate(EndProperty='xyz')
    expect.append({'_type': 'JournalMessage',
                   '_value': 'Finished journal.',
                   'EndProperty': 'xyz'})

    # We're going to pop off expect, so reverse it
    # so that we can check in order.
    expect.reverse()
    navigator = StreamJournalNavigator.new_from_path(path)
    for record in navigator:
        del(record['_thread'])
        del(record['_timestamp'])
        self.assertEquals(record, expect.pop())
    self.assertEquals([], expect)


if __name__ == '__main__':
  unittest.main()
