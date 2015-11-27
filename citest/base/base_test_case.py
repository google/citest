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


class BaseTestCase(unittest.TestCase):
  """Base class for tests.

  There isnt much here in the moment, but more may be added in the future.

  This class is intended to be used in conjunction with the TestRunner,
  though not strictly required. The test runner will call the
  initArgumentParser method introduced by this base class to allow tests to
  add custom bindings.
  """

  def __init__(self, methodName='runTest'):
    """Construct instance.

    Args:
      methodName: [string] The method to run as defined by unittest.TestCase.
    """
    super(BaseTestCase, self).__init__(methodName)
    self.logger = logging.getLogger(__name__)

  def log_start_test(self, name=''):
    """Mark the beginning of a test in the log."""
    if not name:
      # The name of the function calling us.
      name = str(inspect.stack()[1][3])
    self.logger.debug('START %s', name)

  def log_end_test(self, name):
    """Mark the end of a test in the log."""
    if not name:
      # The name of the function calling us.
      name = str(inspect.stack()[1][3])
    underline = '-=' * 39  # separator between tests
    self.logger.debug('END %s\n%s\n', name, underline)

  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    """Adds arguments introduced by the BaseTestCase module.

    Args:
      parser: [argparse.ArgumentParser] instance to add to.
      defaults: [dict] dictionary overriding default values.
    """
    pass
