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


"""Test JournalLogger."""

import json as json_module
import logging
import thread
import unittest

from StringIO import StringIO
from citest.base import (
    JournalLogger,
    JournalLogHandler,
    Journal)
from citest.base import RecordInputStream, RecordOutputStream
from citest.base import set_global_journal

from test_clock import TestClock

_journal_clock = TestClock()
_journal_file = StringIO()
_journal = Journal(now_function=_journal_clock)
_journal.open_with_file(_journal_file)
set_global_journal(_journal)


class JournalLoggerTest(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    logging.getLogger().handlers = []

  def test_record(self):
      logger = logging.getLogger('testrecord')
      record = logger.makeRecord('NAME', 1, 'PATH', 2, 'MSG',
                                 'ARGS', 'EXC_INFO', 'FUNC')

  def test_journal_logger(self):
      offset = len(_journal_file.getvalue())
      logger = JournalLogger('test_journal_logger')
      logger.addHandler(JournalLogHandler(path=None))
      citest_extra = {'foo':'bar', 'format':'FMT'}
      logger.info('Hello, World!', extra={'citest_journal': citest_extra})

      expect = {
          '_value': 'Hello, World!',
          '_type': 'JournalMessage',
          '_level': logging.INFO,
          '_timestamp': _journal_clock.last_time,
          '_thread': thread.get_ident(),
          'foo': 'bar',
          'format': 'FMT',
      }

      entry_str = _journal_file.getvalue()[offset:]
      json_str = RecordInputStream(StringIO(entry_str)).next()
      json_dict = json_module.JSONDecoder(encoding='utf-8').decode(json_str)
      self.assertEqual(expect, json_dict)

  def test_journal_logger_with_custom_message(self):
      offset = len(_journal_file.getvalue())
      logger = JournalLogger(__name__)
      logger.addHandler(JournalLogHandler(path=None))
      citest_extra = {'foo':'bar', '_journal_message':'HELLO, JOURNAL'}
      logger.debug('Hello, World!', extra={'citest_journal': citest_extra})

      expect = {
          '_value': 'HELLO, JOURNAL',
          '_type': 'JournalMessage',
          '_level': logging.DEBUG,
          '_timestamp': _journal_clock.last_time,
          '_thread': thread.get_ident(),
          'foo': 'bar',
          'format': 'pre'
      }

      entry_str = _journal_file.getvalue()[offset:]
      json_str = RecordInputStream(StringIO(entry_str)).next()
      json_dict = json_module.JSONDecoder(encoding='utf-8').decode(json_str)
      self.assertEqual(expect, json_dict)

  def test_nojournal_from_generic_logger(self):
      offset = len(_journal_file.getvalue())
      logger = logging.getLogger('test_nojournal_from_generic_logger')
      logger.addHandler(JournalLogHandler(path=None))
      logger.error('Hello, World!',
                   extra={'citest_journal': {'nojournal':True}})
      self.assertEqual(offset, len(_journal_file.getvalue()))

  def test_journal_log_handler_from_generic_logger(self):
      offset = len(_journal_file.getvalue())
      logger = logging.getLogger('test_journal_log_handler')
      logger.addHandler(JournalLogHandler(path=None))
      citest_extra = {'foo':'bar', '_journal_message':'HELLO, JOURNAL'}
      logger.error('Hello, World!', extra={'citest_journal': citest_extra})

      # Note the extra args arent visible because they arent in the normal
      # LogRecord.
      expect = {
          '_value': 'HELLO, JOURNAL',
          '_type': 'JournalMessage',
          '_level': logging.ERROR,
          '_timestamp': _journal_clock.last_time,
          '_thread': thread.get_ident(),
          'foo': 'bar',
          'format': 'pre',
      }

      entry_str = _journal_file.getvalue()[offset:]
      json_str = RecordInputStream(StringIO(entry_str)).next()
      json_dict = json_module.JSONDecoder(encoding='utf-8').decode(json_str)
      self.assertEqual(expect, json_dict)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JournalLoggerTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
