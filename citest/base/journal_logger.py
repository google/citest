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
import sys
import threading

from .global_journal import (get_global_journal, new_global_journal_with_path)

if sys.version_info[0] > 2:
  basestring = str


def _to_json_if_possible(value):
  """Render value as JSON string if it is json, otherwise as a normal string.

  Args:
    value: [any] The value to render into a string.

  Returns:
    formatted string
  """
  try:
    if isinstance(value, basestring):
      tmp = json_module.JSONDecoder().decode(value)
      return json_module.JSONEncoder(indent=2,
                                     separators=(',', ': ')).encode(tmp)
    else:
      return json_module.JSONEncoder(indent=2,
                                     separators=(',', ': ')).encode(value)
  except (TypeError, ValueError, UnicodeEncodeError):
    return str(value)


class JournalLogger(logging.Logger):
  """This class is only providing Journal-aware convienence functions."""

  __thread_data = threading.local()
  __thread_data.context_stack = []

  @staticmethod
  def delegate(method, *positional_args, **kwargs):
    """Call the method in the underling journal, if there is one.

    This has no effect if we do not have a journal.

    Args:
      method: The method name to call in the logging journal.
      positional_args: The positional args to pass to the method
      kwargs The keyword args to pass to the method.
    """
    journal = get_global_journal()
    if not journal:
      return
    getattr(journal, method)(*positional_args, **kwargs)

  @staticmethod
  def store_or_log(_obj, levelno=logging.INFO, _logger=None, **kwargs):
    """Store the object into the underlying journal (if any), and log it.

    Args:
      _obj: The JsonSnapshotable object to store.
      levelno: [int] The logging debug level.
      _logger: [Logging] The logger to use if overriding this module.
      kwargs: Additional metadata to pass through to the journal.
   """
    journal = get_global_journal()
    if journal is not None:
      journal.store(_obj)
      kwargs = dict(kwargs)
      kwargs['nojournal'] = True

    logger = _logger or logging.getLogger(__name__)
    logger.log(levelno, repr(_obj), extra={'citest_journal': kwargs})

  @staticmethod
  def journal_or_log(_msg, levelno=logging.DEBUG, _logger=None, **kwargs):
    """Writes a log message into the journal (if any) and log it.

    This API is an alternative to logger.log that permits Journal metadata
    to be added. The message is also written into the normal logger API
    but without the additional metadata.

    Args:
      _msg: [string] The log message to write
      levelno: [int] The logging debug level.
      _logger: [Logging] The logger to use if overriding this module.
      kwargs: Additional metadata to pass through to the journal.
    """
    if 'format' not in kwargs:
      # If a format was not specified, then default to 'pre'
      kwargs = dict(kwargs)
      kwargs['format'] = 'pre'

    journal = get_global_journal()
    if journal is not None:
      journal.write_message(_msg, _level=levelno, **kwargs)
      kwargs = dict(kwargs)
      kwargs['nojournal'] = True

    logger = _logger or logging.getLogger(__name__)
    logger.log(levelno, _msg, extra={'citest_journal': kwargs})


  @staticmethod
  def journal_or_log_detail(_msg, _detail, levelno=logging.DEBUG,
                            _logger=None, **kwargs):
    """Log a message and detail.

    This will write into the global journal if any, as well as log it.

    Args:
      _msg: [string] The log message to write.
      _detail: [any] The data detail to log.
      levelno: [int] The logging debug level.
      _logger: [Logging] The logger to use if overriding this module.
      kwargs: Additional metadata to pass through to the journal.
    """
    json_text = _to_json_if_possible(_detail)
    JournalLogger.journal_or_log(
        _msg='{0}\n{1}'.format(_msg, json_text), levelno=levelno,
        _logger=_logger, **kwargs)

  @staticmethod
  def execute_in_context(_title, _callable, **kwargs):
    """
    Shorthand to begin and end a context around a callable.

    This performs additional logging beyond the begin/end context calls
    by logging exceptions thrown out of the context.

    Args:
      _title: [string] The title of the context.
      _callable: [callable] The code to execute in the context.
      kwargs: [kwargs] Passed through to both begin_context and end_context.

    Returns:
      The result of _callable
    """
    JournalLogger.begin_context(_title, **kwargs)
    try:
      result = _callable()
    except:
      ex_type, ex_value, ex_stack = sys.exc_info()
      logging.getLogger(__name__).error(
          'Throwing "%s" out of context=%s: %s\n%s',
          ex_type, _title, ex_value, ex_stack)
      raise
    finally:
      JournalLogger.end_context()
    return result

  @staticmethod
  def begin_context(_title, **kwargs):
    """
    Mark the beginning of a context in the journal.

    Future entries will be associated with this context until end_context()
    is called. Contexts can be nested.

    Args:
      _title: [string] The title of the context.
    """
    context_stack = JournalLogger.__thread_data.context_stack
    logging.getLogger(__name__).debug(
        '+context[%d]: %s', len(context_stack), _title,
        extra={'citest_journal':{'nojournal':True}})
    context_stack.append(_title)

    journal = get_global_journal()
    if journal is not None:
      journal.begin_context(_title, **kwargs)

  @staticmethod
  def end_context(**kwargs):
    """Mark the ending of the current context within the journal."""
    context_stack = JournalLogger.__thread_data.context_stack
    context_stack.pop()
    logging.getLogger(__name__).debug(
        '-context[%d]', len(context_stack),
        extra={'citest_journal':{'nojournal':True}})
    journal = get_global_journal()
    if journal is not None:
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
