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


"""Implements TestRunner class.

The TestRunner class is used to control the overall execution and reporting
of tests. It is a unittest.TestRunner that will setup and tear down the global
test environment, and delegate to another unittest.TestRunner to run the
actual tests. This class wraps the delegate by setting up the bindings and
reporting journal while letting the injected TestRunner perform the actual
running and standard reporting hooks used by other tools.
"""

# Standard python modules.
import argparse
import ast
import datetime
import logging
import logging.config
import os.path
import sys
import unittest

# Our modules.
from . import args_util
from . import (Journal, JsonSnapshotable)

# If a -log_config is not provided, then use this.
_DEFAULT_LOG_CONFIG = """{
 'version':1,
 'disable_existing_loggers':True,
 'formatters':{
 'timestamped':{
   'format':'%(asctime)s %(message)s',
   'datefmt':'%H:%M:%S'
  }
 },
 'handlers':{
   'console':{
   'level':'WARNING',
   'class':'logging.StreamHandler',
   'formatter':'timestamped'
  },
  'file':{
   'level':'DEBUG',
   'class':'logging.FileHandler',
   'formatter':'timestamped',
   'filename':'$LOG_DIR/$LOG_FILENAME',
   'mode':'w'
  }
 },
  'loggers':{
  '': {
   'level':'DEBUG',
   'handlers':['console', 'file']
  }
 }
}
"""


class TestRunner(object):
  """Provides additional reporting for existing TestRunners.

  The TestRunner delegates to an existing injected unittest TestRunner
  (e.g. TextTestRunner) to run tests.

  It is assumed that where effects are not desired to be shared, the test
  will either undo the effects as part of the test or contribute an additional
  test that will undo the effects and have that test execute before other
  tests that do not want the side effects.

  The runner maintains a map of bindings to different parameters available to
  tests. The bindings dictionary is exposed for direct injection of hardcoded
  values without overrides.

  The runner configures logging using the LOG_CONFIG key to get the config
  filename, if any. If no LOG_CONFIG is provided, the a default will be used.
  The LOG_CONFIG can reference additional |$KEY| variables, which will be
  resolved using the binding for |KEY|.
  """

  __global_runner = None

  @property
  def options(self):
    """Returns a ArgumentParserNamespace with the commandline option values.

    The intention is for the bindings to be a more complete collection, but
    options are here for convienence in controlled circumstances
    (e.g. 'private' options).
    """
    return self.__options

  @property
  def bindings(self):
    """Returns a dictionary with name/value bindings.

    The keys in the binding dictionary are upper case by convention to help
    distinguish them. The default bindings are derived from the "options",
    however the program is free to add additional bindings.
    """
    return self.__bindings

  @property
  def default_binding_overrides(self):
    """A dictionary keyed by the binding key used to initialize options.

    The purpose of this dictionary is to provide default values when adding
    argumentParser arguments. This dictionary is passed to the
    initArgumentParser method in the BaseTestCase when initializing the
    ArgumentParser. Programs can use this to inject the default submodule
    values they'd like to override.
    """
    return self.__default_binding_overrides

  @staticmethod
  def global_runner():
    """Returns the TestRunner instance.

    Presumably there is only one.
    """
    if TestRunner.__global_runner is None:
      raise BaseException('TestRunner not yet instantiated')
    return TestRunner.__global_runner

  @classmethod
  def main(cls, runner=None,
           default_binding_overrides=None,
           test_case_list=None):
    """Implements a main method for running tests.

    This main will instantiate an instance of the class |cls| then
    pass control to the _do_main method on the instantiated runner.

    Args:
      runner: If provided, then delegate to this runner to run the tests.
      default_binding_overrides: Provides a means to inject default values
          to use for bindings.
      test_case_list: If provided, a list of test cases to run.
    """
    runner = cls(runner=runner)
    runner.set_default_binding_overrides(default_binding_overrides)
    return runner._do_main(test_case_list=test_case_list)

  def set_default_binding_overrides(self, overrides):
    """Provides a means for setting the default_binding_overrides attribute.

    This is intentionall not an assignment because it is not intended to be
    called, but is here in case it is no possible to use the "main()" method.
    """
    self.__default_binding_overrides = overrides or {}

  def _do_main(self, default_binding_overrides=None, test_case_list=None):
    """Helper function used by main() once a TestRunner instance exists."""
    # pylint: disable=unused-argument
    # default_binding_overrides is declared as a prototype for derived classes
    # but not actually used here.
    logger = logging.getLogger(__name__)
    logger.info('Building test suite')
    suite = self.build_suite(test_case_list)

    # Create some separation in logs
    logger.info('Finished Setup. Start Tests\n'
                + ' ' * (8 + 1)  # for leading timestamp prefix
                + '---------------------------\n')
    result = self.run(suite)
    return len(result.failures) + len(result.errors)

  def __init__(self, runner=None):
    TestRunner.__global_runner = self
    self.__delegate = runner or unittest.TextTestRunner(verbosity=2)
    self.__options = None
    self.__bindings = {}
    self.__default_binding_overrides = {}
    self.__journal = None

  def run(self, obj_or_suite):
    """Run tests.

    Args:
      obj_or_suite: The TestCase or TestSuite to run.
    """
    self._prepare()

    logger = logging.getLogger(__name__)
    logger.info('Running tests')

    try:
      result = self.__delegate.run(obj_or_suite)
    finally:
      if sys.exc_info()[0] != None:
        sys.stderr.write('Terminated early due to an exception\n')
      self._cleanup()

    return result

  def initArgumentParser(self, parser, defaults=None):
    """Adds arguments introduced by the TestRunner module.

    Args:
      parser: argparse.ArgumentParser instance to add to.
    """
    # Normally we want the log file name to reflect the name of the program
    # we are running, but we might not be running one (e.g. in interpreter).
    try:
      basename = os.path.basename(sys.argv[0])
      main_filename = os.path.splitext(basename)[0] + '.log'
    except IndexError:
      main_filename = 'debug.log'

    defaults = defaults or {}
    parser.add_argument('--log_dir', default=defaults.get('LOG_DIR', '.'))
    parser.add_argument('--log_filename',
                        default=defaults.get('LOG_FILENAME', main_filename))
    parser.add_argument(
        '--log_config', default=defaults.get('LOG_CONFIG', ''),
        help='Path to text file containing custom logging configuration. The'
        ' contents of this path can contain variable references in the form'
        ' $KEY where --KEY is a command-line argument that whose value should'
        ' be substituted. Otherwise this is a standard python logging'
        ' configuration schema as described in'
        ' https://docs.python.org/2/library/logging.config.html'
        '#logging-config-dictschema')

  def start_logging(self):
    """Setup default logging from the --log_config parameter."""
    text = _DEFAULT_LOG_CONFIG
    path = self.bindings.get('LOG_CONFIG', None)
    if path:
      try:
        with open(path, 'r') as f:
          text = f.read()
      except Exception as ex:
        print 'ERROR reading LOGGING_CONFIG from {0}: {1}'.format(path, ex)
        raise
    config = ast.literal_eval(args_util.replace(text, self.bindings))
    logging.config.dictConfig(config)
    path = os.path.join(
        self.bindings['LOG_DIR'], self.bindings['LOG_FILENAME'])
    os.chmod(path, 0600)


  def start_report_journal(self):
    """Sets up report_journal and output file for high level reporting."""
    if self.__journal is not None:
      raise ValueError('report_journal already started.')

    dirname = self.bindings.get('LOG_DIR', '.')
    filename = os.path.basename(self.bindings.get('LOG_FILENAME'))
    filename = os.path.splitext(filename)[0] + '.journal.json'

    journal_file = open(os.path.join(dirname, filename), 'w')
    os.fchmod(journal_file.fileno(), 0600)  # Protect sensitive data.
    self.__journal = Journal()
    self.__journal.open_with_file(journal_file)

  def report(self, obj):
    """Add object to report.

    Args:
      obj: The object to write into the report.
    """
    if isinstance(obj, JsonSnapshotable):
      self.__journal.store(obj)
    else:
      raise '{0} is not JsonSnashotable\n{1}'.format(type(obj), obj)

  def finish_report_journal(self):
    """Finish the reporting journal and close the file."""
    if self.__journal is None:
      return
    self.__journal.terminate()
    self.__journal = None

  def build_suite(self, test_case_list):
    """Build the TestSuite of tests to run."""
    if not test_case_list:
      raise ValueError('No test cases provided.')

    loader = unittest.TestLoader()

    # TODO(ewiseblatt): 20150521
    # This doesnt seem to take effect. The intent here is to not sort the order
    # of tests. But it still is. So I've renamed the tests to lexographically
    # sort in place. Leaving this around anyway in hopes to eventually figure
    # out why it doesnt work.
    loader.sortTestMethodsUsing = None

    suite = unittest.TestSuite()
    for test in test_case_list:
      suite.addTests(loader.loadTestsFromTestCase(test))
    return suite

  def _prepare(self):
    """Suite helper function finishes initialization of global context.

    This includes processing command-line arguments to set the bindings in
    the runner, and initializing the reporting journal.
    """
    # Customize commandline arguments
    parser = argparse.ArgumentParser()
    self.initArgumentParser(parser, defaults=self.default_binding_overrides)
    self.__options = parser.parse_args()
    self.__bindings.update(args_util.parser_args_to_bindings(self.__options))

    self.start_logging()
    self.start_report_journal()

  def _cleanup(self):
    """Helper function when running a suite for cleaning up the global context.

    This incudes closing out the report.
    """
    self.finish_report_journal()
