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

"""
Unit tests for the citest.base.TestRunner's ability to execute unit tests.

Because the fixtures below are normal test fixture, the unittest loader is
going to want to run their tests. However, the fixtures are really intended
to be used from our test runner. To ensure we're using it, we'll create another
fixture that will use our runner to run this test.

In order to distinguish between the two contexts, we will use the global
"in_test_main" variable to skip the tests called from the global runner and
only execute from the embedded runner within the other test fixture declared
below.

There are a number of fixtures here. The gist is that one fixture is the
actual test fixture exported by this module (TestRunnerTestCase).

The others are test fixtures used by the test runner that fixture will use
to perform a unit test. Those fixtures are used to perform the test of the
TestRunner, but in the context of running a test (the main() call in the
aforementioned TestCase). There are a couple fixtures testing the handling
if adding new commandline arguments and an overall testing fixture.
"""

import os.path
import sys
import unittest
import __main__

from citest.base import (
    BaseTestCase,
    ConfigurationBindingsBuilder,
    TestRunner)


# pylint: disable=invalid-name
# pylint: disable=global-statement
call_check = []
in_test_main = False


class TestingTestRunner(TestRunner):
  """Overloaded TestRunner to support the fixtures below.

  We need to supress the journal from terminating or else future tests will
  raise an exception when attempting to log because the journal log handler
  that intercepts these calls will attempt to write to the closed journal.
  """

  terminate_calls = 0   # verifies we called _terminate_and_flush_journal once

  def _terminate_and_flush_journal(self):
    """Override base method so we dont actually terminate the journal."""
    TestingTestRunner.terminate_calls += 1


class TestRunnerTest(BaseTestCase):
  """A Test fixture used to test the TestRunner.

  This leaves out binding related tests for the bindings fixtures below.
  """

  def setUp(self):
    """Disable tests called from the global fixture."""
    if not in_test_main:
      raise unittest.SkipTest('not in test runner yet.')

  def test_was_called(self):
    """Mark a test as having been run so we know we are calling tests."""
    # Confirms that our tests run.
    call_check.append(self.__class__)

  def test_shared_data_without_extra_bindings(self):
    """Tests global singleton data management provided by TestRunner."""
    # pylint: disable=missing-docstring
    # pylint: disable=too-few-public-methods
    class MyData(object):
      @property
      def bindings(self):
        return self.__bindings
      def __init__(self, bindings):
        self.__bindings = bindings

    # Configures from our runner's properties.
    a = TestRunner.get_shared_data(MyData)
    self.assertEquals('MyTestBindingValue', a.bindings.get('test_binding'))

    # Acts as singleton
    b = TestRunner.get_shared_data(MyData)
    self.assertEquals(a, b)

  def test_shared_data_with_extra_bindings(self):
    """Tests global singleton data management provided by TestRunner."""
    # pylint: disable=missing-docstring
    # pylint: disable=too-few-public-methods
    class MyData(object):
      @classmethod
      def init_bindings_builder(cls, builder, defaults=None):
        defaults = defaults or {}
        builder.add_argument(
            '--data', default=defaults.get('TEST_DATA', 'MyData'))
      @property
      def bindings(self):
        return self.__bindings
      def __init__(self, bindings):
        self.__bindings = bindings

    # Configures from our runner's properties.
    a = TestRunner.get_shared_data(MyData)
    self.assertEquals('MyData', a.bindings.get('data'))

    # Acts as singleton
    b = TestRunner.get_shared_data(MyData)
    self.assertEquals(a, b)


class TestBindingOrParamFixture(BaseTestCase):
  """A Test fixture used to test the TestRunner.

  This is used to verify that we are calling multiple fixtures, and
  also using the DEPRECATED initArgumentParser method to initialize argparser.
  """

  def setUp(self):
    """Disable tests called from the global fixture."""
    if not in_test_main:
      raise unittest.SkipTest('not in test runner yet.')

  def test_was_called(self):
    """Mark a test as having been run so we know we are calling tests."""
    # Confirms that our tests run.
    call_check.append(self.__class__)

  def test_init_bindings_builder(self):
    """Verify the builtin bindings."""
    builder = ConfigurationBindingsBuilder()
    TestRunner.global_runner().init_bindings_builder(builder)
    bindings = builder.build()
    self.assertEquals('.', bindings.get('log_dir'))
    self.assertEquals(os.path.splitext(os.path.basename(__main__.__file__))[0],
                      bindings.get('log_filebase'))

    # While not necessarily a design criteria, the implementation has all
    # the bindings added by all the fixtures.
    self.assertEquals('MyTestParamValue', bindings.get('TEST_PARAM'))
    self.assertEquals('MyTestBindingValue', bindings.get('TEST_BINDING'))

  def test_bindings(self):
    """Verify bindings are set on the runner."""

    bindings = TestRunner.global_runner().bindings
    self.assertEquals('.', bindings['LOG_DIR'])
    self.assertEquals(
        os.path.splitext(os.path.basename(__main__.__file__))[0],
        bindings['LOG_FILEBASE'])

    # While not necessarily a design criteria, the implementation has all
    # the bindings added by all the fixtures.
    self.assertEquals('MyTestParamValue', bindings.get('TEST_PARAM'))
    self.assertEquals('MyTestBindingValue', bindings.get('TEST_BINDING'))


class TestParamFixture(TestBindingOrParamFixture):
  """Verify Fixture using initArgumentParser."""

  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    """Override base method to check that command line args are handled."""
    defaults = defaults or {}
    parser.add_argument('--test_param', default=defaults.get('TEST_PARAM'))


class TestBindingsFixture(TestBindingOrParamFixture):
  """Verify Fixture using init_bindings_builder."""

  @classmethod
  def init_bindings_builder(cls, builder, defaults=None):
    """Override base method to check that command line args are handled."""
    defaults = defaults or {}
    builder.add_argument('--test_binding', default=defaults.get('TEST_BINDING'))


class TestRunnerTestCase(unittest.TestCase):
  """The actual test fixture for testing citest.base.TestRunner"""

  def test_main(self):
    """Test citest.base.TestRunner.main() invocation."""
    global in_test_main

    test_fixtures = [TestRunnerTest, TestParamFixture, TestBindingsFixture]
    argv = sys.argv
    try:
      in_test_main = True
      sys.argv = [sys.argv[0],
                  '--test_binding', 'MyTestBindingValue',
                  '--test_param', 'MyTestParamValue']
      result = TestingTestRunner.main(test_case_list=test_fixtures)
    finally:
      in_test_main = False
      sys.argv = argv

    self.assertEquals(0, result)
    self.assertEquals(call_check, test_fixtures)
    self.assertEquals(1, TestingTestRunner.terminate_calls)


if __name__ == '__main__':
  sys.exit(TestRunner.main(test_case_list=[TestRunnerTestCase]))
