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


"""Specialized logging.Logger and logging.LogHandler to write into journals."""


import json as json_module
import logging
import thread as thread_module

from .global_journal import (get_global_journal, new_global_journal_with_path)


def _to_json_if_possible(value):
  """Render value as JSON string if it is json, otherwise as a normal string.

  Args:
    value: [any] The value to render into a string.

  Returns:
    formatted string
  """
  try:
    if isinstance(value, basestring):
      tmp = json_module.JSONDecoder(encoding='utf-8').decode(value)
      return json_module.JSONEncoder(indent=2,
                                     encoding='utf-8',
                                     separators=(',', ': ')).encode(tmp)
    else:
      return json_module.JSONEncoder(indent=2,
                                     encoding='utf-8',
                                     separators=(',', ': ')).encode(value)
  except (ValueError, UnicodeEncodeError):
    return str(value)


class JournalLogger(logging.Logger):
  """This class is only providing Journal-aware convienence functions."""

  @staticmethod
  def journal_or_log(_msg, levelno=logging.DEBUG,
                     _module=None, _alwayslog=False, **kwargs):
    """Writes a log message into the journal (if there is one) or logging API.

    This API is an alternative to logger.log that permits Journal metadata
    to be added. If there is no journal, then the message will be written into
    the normal logger API without the additional metadata.

    Args:
      _msg: [string] The log message to write
      levelno: [int] The logging debug level.
      _module: [string] The logging module name, or none for this.
      _alwayslog [bool] If True then always log.
          Otherwise only journal but only log if there is no journal.
      kwargs: Additional metadata to pass through to the journal.
    """
    if not 'format' in kwargs:
      # If a format was not specified, then default to 'pre'
      kwargs = dict(kwargs)
      kwargs['format'] = 'pre'
    JournalLogger._helper(
        _msg, levelno=levelno, _alwayslog=_alwayslog, _module=_module,
        metadata=kwargs)

  @staticmethod
  def _helper(_msg, levelno, _alwayslog, _module, metadata):
    """Helper class for log()"""
    journal = get_global_journal()
    if _alwayslog or journal is None:
      logging.getLogger(_module or __name__).log(
          levelno, _msg, extra={'citest_journal': metadata})
    else:
      journal.write_message(_msg,
                            _level=levelno,
                            _thread=thread_module.get_ident(),
                            **metadata)

  @staticmethod
  def journal_or_log_detail(_msg, _detail, levelno=logging.DEBUG,
                            _module=None, _alwayslog=False, **kwargs):
    """Log a message and detail.

    If there is a global journal and not _alwayslog then writes this there.
    Otherwise log it. The reason for the distinction is so that we can filter
    down normal logs.

    Args:
      _msg: [string] The log message to write.
      _detail: [any] The data detail to log.
      levelno: [int] The logging debug level.
      _module: [string] The logging module name, or none for this.
      _alwayslog [bool] If True then always log.
          Otherwise only journal but only log if there is no journal.
      kwargs: Additional metadata to pass through to the journal.
    """
    # It would be nice to just write json into the file here, especially so
    # we dont need to format it now and can leave it to the renderer.
    # However we'd like to add a message and complement it with the json data.
    # We dont want the renderer on the other side to see an aggregated json.
    #
    # TODO(ewiseblatt): 20160125
    # Ideally we need to add a metadata attribute for the message and make the
    # renderer aware, but that requires some more thought about how to
    # standardize and will have other impact, so putting it off for now.
    json_text = _to_json_if_possible(_detail)
    JournalLogger.journal_or_log(
        _msg='{0}\n{1}'.format(_msg, json_text), levelno=levelno,
        _module=_module, _alwayslog=_alwayslog, **kwargs)

  @staticmethod
  def begin_context(_title, **kwargs):
    """
    Mark the beginning of a context in the journal.

    Future entries will be associated with this context until end_context()
    is called. Contexts can be nested.

    Args:
      _title: [string] The title of the context.
    """
    journal = get_global_journal()
    journal.begin_context(_title, **kwargs)
    logging.getLogger(__name__).debug(
        '+context %s', _title, extra={'citest_journal':{'nojournal':True}})

  @staticmethod
  def end_context(**kwargs):
    """Mark the ending of the current context within the journal."""
    logging.getLogger(__name__).debug(
        '-context',
        extra={'citest_journal':{'nojournal':True}})
    journal = get_global_journal()
    if journal:
      journal.end_context(**kwargs)


class JournalLogHandler(logging.StreamHandler):
  """A standard log handler that will write journal entries.

  This handler is intended to be plugged into the normal python logging
  framework to mirror normal logging messages into the journal.

  Note that log messages are unstructured text, but the journal prefers
  structured data so that rendering can be more intelligent. Sometimes a
  call site may wish to log structured messages into the journal and
  unstructured to other loggers. Sometimes it may wish to log only to
  the journal (e.g. highly detailed data) and sometimes only to other loggers
  (e.g. because the journal was already given highly detailed data).

  The handler recognizes LogRecord attribute 'citest_journal', which is
  a dictionary that can be used for passing metadata to the journal and other
  parameters to this handler. The [optional] parameters stripped by the handler
  are:
     nojournal [bool]:  If True do not log the message into the journal.
     _joural_message [string]: Journal this instead of the LogRecord message.
  """

  def __init__(self, path):
    """Construct a handler using the global journal.

    Ideally we'd like to inject a journal in here.
    But the logging config takes a string specification so we'd need
    a complicated way to say we want to use the global journal. So lets just
    do that.

    Args:
      path: [string] Specifies the path for the global journal, if it does not
          already exist.
    """
    super(JournalLogHandler, self).__init__()
    self.__journal = get_global_journal()
    if self.__journal is None:
      self.__journal = new_global_journal_with_path(path)

  def emit(self, record):
    """Emit the record to the journal."""
    journal_extra = getattr(record, 'citest_journal', {})
    if journal_extra.get('nojournal', False):
      # See class description
      return
    journal_extra.pop('nojournal', None)
    journal_extra.setdefault('format', 'pre')
    message = record.getMessage()
    message = journal_extra.pop('_journal_message', message)

    self.__journal.write_message(message,
                                 _level=record.levelno,
                                 _thread=record.thread,
                                 **journal_extra)

  def flush(self):
    """Implements the LogHandler interface."""
    # The journal always flushes. Since we are using the global journal,
    # which is accessable outside this logger, it needs to already be flushed
    # to allow interleaving writers to preserve ordering.
    pass

