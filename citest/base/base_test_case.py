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


"""Implements BaseTestCase class.

The BaseTestCase class is derived from unittest.TestCase, providing some
boilerplate and common routines on top of it. The class makes some changes
to accomodate for differences in writing integration tests from unit tests.
In particular, whereas unit tests are cheap, can be run in any order and have
no side effects affecting other tests, integration tests may [intentionally]
have lasting side effects that other tests depend on due their cost to run.

The BaseTestCase adds command line argument processing using the standard
argparse.ArgumentParser. It produces a "binding" dictionary of all the
commandline argument key/value pairs (except keys are in upper case) that
then become available to tests so that their configuration can be easily
tweaked.

The BaseTestCase adds logging support where it can set up standard logging
configuration so that it logs details to persistent file that can be consulted
later without cluttering the console, which only displays warnings and errors.
Additionally, each entry is timestamped.
"""

# Standard python modules.
import inspect
import logging
import unittest

from .journal_logger import JournalLogger


class _TestProcessingStep(object):
  SETUP = 0
  EXECUTE = 1
  TEARDOWN = 2


class BaseTestCase(unittest.TestCase):
  """Base class for tests.

  There isnt much here in the moment, but more may be added in the future.

  This class is intended to be used in conjunction with the TestRunner,
  though not strictly required. The test runner will call the
  initArgumentParser method introduced by this base class to allow tests to
  add custom bindings.
  """

  @property
  def logger(self):
    """Returns the logger for the fixture."""
    return logging.getLogger(__name__)

  def __init__(self, methodName='runTest'):
    """Construct instance.

    Args:
      methodName: [string] The method to run as defined by unittest.TestCase.
    """
    # We're going to use the base class to invoke methods since
    # it implements the protocol for calling setup/teardown and other
    # workflow. However the base class doesnt provide hooks or means for
    # us to distinguish before/after method calls or catch exceptions
    # and failures or join the logs the way we are.
    #
    # To work around this, we'll wrap the fixtures method for this test with
    # our own wrapper. Since the base class is based on the name of this method
    # and uses it for reporting, we'll preserve the name, but overwrite the
    # implementation with our wrapper, then have our wrapper delegate to the
    # original intended method.
    self.__method_name = methodName
    self.__method = getattr(self, self.__method_name)

    self.__in_step = None
    setattr(self, self.__method_name, self.__wrap_method)
    super(BaseTestCase, self).__init__(methodName)

  def __wrap_method(self):
    # Wraps the calls to the actual test method so we have visibility.
    #
    # When __call__ passes control to the base class, it will call this method
    # after it has called setup. When we pass control back after this method,
    # the base class will call teardown.
    #
    # Note this comment is not a string so that the TestRunner
    # will not reflect on its comment.

    self.__end_step_context(relation='VALID')
    self.__in_step = _TestProcessingStep.SETUP

    JournalLogger.begin_context('Execute')
    self.__method()

    JournalLogger.end_context(relation='VALID')
    self.__in_step = _TestProcessingStep.TEARDOWN

    self.__begin_step_context()

  def __begin_step_context(self):
    if (self.__in_step != _TestProcessingStep.SETUP
        and self.__in_step != _TestProcessingStep.TEARDOWN):
      raise ValueError('Unexpected step={0}'.format(self.__in_step))
    JournalLogger.begin_context(
        'setUp'
        if self.__in_step == _TestProcessingStep.SETUP
        else 'tearDown')

  def __end_step_context(self, relation):
    if self.__in_step is None:
      return
    JournalLogger.end_context(relation=relation)

  def __call__(self, result=None):
    """Wraps the base class fixture heuristics that run an individual test."""
    if result is None:
      result = self.defaultTestResult()

    num_failures = len(result.failures)
    num_errors = len(result.errors)
    method_name = self.__method_name
    self.__in_step = _TestProcessingStep.SETUP
    try:
      doc = {'_doc': self.__method.__doc__} if self.__method.__doc__ else {}
      JournalLogger.begin_context('Test "{0}"'.format(method_name),
                                  **doc)
      self.__begin_step_context()
      super(BaseTestCase, self).__call__(result)
    finally:
      test_relation = None
      error_details = None
      if len(result.errors) > num_errors:
        test_relation = 'ERROR'
        error_details = result.errors[num_errors]
      elif len(result.failures) > num_failures:
        test_relation = 'INVALID'
      else:
        test_relation = 'VALID'

      if error_details is not None:
        JournalLogger.journal_or_log_detail(
            'Raised Exception', error_details[1],
            levelno=logging.ERROR, format='pre', _logger=self.logger)

      self.__end_step_context(relation=test_relation)
      self.__in_step = None

      JournalLogger.end_context(relation=test_relation)

  def log_start_test(self, name=''):
    """Mark the beginning of a test in the log."""
    if not name:
      # The name of the function calling us.
      name = str(inspect.stack()[1][3])
    self.logger.debug('START %s', name,
                      extra={'citest_journal': {'nojournal': True}})

  def log_end_test(self, name):
    """Mark the end of a test in the log."""
    if not name:
      # The name of the function calling us.
      name = str(inspect.stack()[1][3])
    underline = '-=' * 39  # separator between tests
    self.logger.debug('END %s\n%s\n', name, underline,
                      extra={'citest_journal': {'nojournal': True}})

  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    """Adds arguments introduced by the BaseTestCase module.

    Args:
      parser: [argparse.ArgumentParser] instance to add to.
      defaults: [dict] dictionary overriding default values.
    """
    # pylint: disable=invalid-name
    pass
