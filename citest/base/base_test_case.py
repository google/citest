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


"""Implements BaseTestScenario and BaseTestCase classes.

The BaseTestCase class is derived from unittest.TestCase, providing some
boilerplate and common routines on top of it. The class makes some changes
to accomodate for differences in writing integration tests from unit tests.
In particular, whereas unit tests are cheap, can be run in any order and have
no side effects affecting other tests, integration tests may [intentionally]
have lasting side effects that other tests depend on due their cost to run.

The BaseTestCase adds command line argument processing using the standard
argparse.ArgumentParser. It produces a "binding" dictionary of all the
commandline argument key/value pairs (except keys are in upper case) that
then become available to tests so that their configuration can be easily tweaked.

The BaseTestCase adds logging support where it can set up standard logging
configuration so that it logs details to persistent file that can be consulted
later without cluttering the console, which only displays warnings and errors.
Additionally, each entry is timestamped.

The BaseTestCase is designed to factor out test content into a separate class
so that the BaseTestCase handles control for running the test and a "scenario"
class is used to capture the actual test data shared among tests.
The BaseTestScenario does not actually do anything and can be ignored except
the base class will construct one.
"""

# Standard python modules.
import argparse
import ast
import datetime
import inspect
import logging
import logging.config
import os.path
import re
import sys
import unittest

# Our modules.
from . import args_util
from . import html_scribe
from .scribe import Doodle


# If a -log_config is not provided, then use this.
_DEFAULT_LOG_CONFIG = (
"{"
" 'version':1,"
" 'disable_existing_loggers':True,"
" 'formatters':{"
" 'timestamped':{"
"   'format':'%(asctime)s %(message)s',"
"   'datefmt':'%H:%M:%S'"
"  }"
" },\n"
" 'handlers':{"
"  'console':{"
"   'level':'WARNING',"
"   'class':'logging.StreamHandler',"
"   'formatter':'timestamped'"
"  },\n"
"  'file':{"
"   'level':'DEBUG',"
"   'class':'logging.FileHandler',"
"   'formatter':'timestamped',"
"   'filename':'$LOG_DIR/$LOG_FILENAME',"
"   'mode':'w'"
"  }"
" },\n"
" 'loggers':{"
"  '':{"
"   'level':'DEBUG',"
"   'handlers':['console', 'file']"
"  }"
" }"
"}"
)


class BaseTestScenario(object):
  """Base class for scenario data shared across multiple different test cases.

  This class could fold into the BaseTestCase, but it might make tests easier
  to read by separating responsibilities as well as providing global data
  across tests. For example command-line flags. This class is responsible for
  managing the testable agent and configuration information.

  This class does not really define much behavior. It just manages
  a set of parameters. The intent is for specialized classes to
  define the OperationTestCases, using the parameters to determine
  the final values to use.
  """

  @property
  def bindings(self):
    return self._bindings

  @property
  def scenario(self):
    return self._scenario

  def __init__(self, bindings):
    """Constructs instance.

    Args:
      bindings: Dictionary of key/value configuration values.
        The keys are in upper case. The actual keys are not standardized,
        rather the scenarios may have a set of parameters that they use
        for their needs.
    """
    self._bindings = bindings

  def substitute_variables(self, s):
    """Substitute $KEY with the bound value of KEY.

    Returns:
      Copy of s with bound variables substituted with their values.
    """
    return args_util.replace(s, self._bindings)

  @classmethod
  def initArgumentParser(cls, parser):
    """Adds arguments introduced by the BaseTestCase module.

    Args:
      parser: argparse.ArgumentParser instance to add to.
    """
    pass


class BaseTestCase(unittest.TestCase):
  """Base class for tests.

  Properties:
    bindings: A dictionary of strings keyed by upper case parameters.
      The dictionary is initialized by setUpClass from the command line
      arguments, but the keys are all upper-cased.
  """
  _scenario = None

  @staticmethod
  def make_scenario(scenarioClass, bindings):
    return scenarioClass(bindings)

  @property
  def bindings(self):
    return self._scenario.bindings

  @property
  def scenario(self):
    return self._scenario

  @property
  def reportScribe(self):
    return self._reportScribe

  def __init__(self, methodName='runTest'):
    """Construct instance.

    Args:
      methodName: The methodName to run as defined by unittest.TestCase.
    """
    if not self._scenario:
      print ('\n*** WARNING: {0} was not initialized with a scenario.'
             '\n*** Probably because you did not call BaseTestCase.main().'
             '\n*** This could be because this test is being run indirectly.'
             '\n*** Assuming BaseTestScenario.\n'
             .format(self.__class__.__name__))
      self.__class__.setupScenario(BaseTestScenario)
    super(BaseTestCase, self).__init__(methodName)
    self.logger = logging.getLogger(__name__)

  def log_start_test(self, name=''):
    if not name:
      # The name of the function calling us.
      name = str(inspect.stack()[1][3])
    self.logger.debug('START %s', name)

  def log_end_test(self, name):
    if not name:
      # The name of the function calling us.
      name = str(inspect.stack()[1][3])
    label = 'END ' + name
    underline = '-=' * 39  # separator between tests
    self.logger.debug('END %s\n%s\n', name, underline)

  def setUp(self):
    if not self.isTestEnabled(self.id()):
      self.skipTest('Does not match --enable_test_regex.')

  def isTestEnabled(self, name):
    regex = self.bindings.get('ENABLE_TEST_REGEX', None)
    if not regex:
      return True

    return re.search(regex, name)

  @classmethod
  def initArgumentParser(cls, parser):
    """Adds arguments introduced by the BaseTestCase module.

    Args:
      parser: argparse.ArgumentParser instance to add to.
    """
    # This is used by IntegrationTest to filter individual test cases to run.
    parser.add_argument(
       '--enable_test_regex',
       help='If defined then only execute tests whose name matches this regex'
       ' value.')

    # Normally we want the log file name to reflect the name of the program
    # we are running, but we might not be running one (e.g. in interpreter).
    try:
      main_filename = os.path.splitext(os.path.basename(sys.argv[0]))[0] + '.log'
    except:
      main_filename = 'debug.log'

    parser.add_argument('--log_dir', default='.')
    parser.add_argument('--log_filename', default=main_filename)
    parser.add_argument(
      '--log_config', default='',
      help='Path to text file containing custom logging configuration. The'
      ' contents of this path can contain variable references in the form $KEY'
      ' where --KEY is a command-line argument that whose value should be'
      ' substituted. Otherwise this is a standard python logging configuration'
      ' schema as described in'
      ' https://docs.python.org/2/library/logging.config.html'
      '#logging-config-dictschema')

  # TODO(ewiseblatt): 20150807
  # This probably should not be a class method. It is probably in something
  # more global, like the test runner, which is injected into the instances
  # where it is already setup. However the runner isnt fleshed out and we
  # dont have a clear way to inject it into instances so we're just hacking
  # it into the class.
  @classmethod
  def startReportScribe(cls, bindings):
    """Sets up reportScribe and output file for high level reporting.

    Args:
      bindings: A dictionary of strings keyed by upper case parameters.
         The LOG_DIR and LOG_FILENAME will be used, but with html extension)
         so the report file will parallel the normal logging file.
    """
    dir = bindings.get('LOG_DIR', '.')
    filename = os.path.basename(bindings.get('LOG_FILENAME'))
    filename = os.path.splitext(filename)[0] + '.html'
    title = '{program} at {time}'.format(
        program=os.path.basename(sys.argv[0]),
        time=datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    cls._reportScribe = html_scribe.HtmlScribe()
    out = Doodle(cls._reportScribe)
    cls._reportScribe.write_begin_html_document(out, title)
    out.write(
        '<div class="title">{title}</div>\n'.format(title=title))
    cls._reportScribe.write_key_html(out)
    cls._reportFile = open('{0}/{1}'.format(dir, filename), 'w')
    cls._reportFile.write(str(out))

  # TODO(ewiseblatt): 20150807
  # This doesnt really belong here. It is here because
  # it complements startReportScribe, which is here as noted above.
  @classmethod
  def finishReportScribe(cls):
    """Finish the reporting scribe and close the file."""
    out = Doodle(cls._reportScribe)
    cls._reportScribe.write_end_html_document(out)
    cls._reportFile.write(str(out))
    cls._reportFile.close()
    cls._reportScribe = None
    cls._reportFile = None

  # TODO(ewiseblatt): 20150807
  # Same concerns as startReportScribe.
  @classmethod
  def report(cls, obj):
    cls._reportFile.write(cls._reportScribe.render_to_string(obj))

  # TODO(ewiseblatt): 20150807
  # Same concerns as startReportScribe.
  @classmethod
  def startLogging(cls, bindings):
    """Setup default logging from the --log_config parameter.

    Args:
      bindings: dictionary of configuration parameter bindings.
        This uses the LOG_CONFIG key to get the config filename, if any.
        If no LOG_CONFIG is provided, the default configuration will be used.
        The LOG_CONFIG file may reference additional |$KEY| variables, which
        will be resolved using the binding for |KEY|.
    """
    text = _DEFAULT_LOG_CONFIG
    path = bindings.get('LOG_CONFIG', None)
    if path:
      try:
        with open(path, 'r') as f:
          text = f.read()
      except Exception as e:
        print 'ERROR reading LOGGING_CONFIG from {0}: {1}'.format(path, e)
        raise
    config = ast.literal_eval(args_util.replace(text, bindings))
    logging.config.dictConfig(config)

  @classmethod
  def buildSuite(cls):
    """Buid the TestSuite of tests to run."""
    loader = unittest.TestLoader()

    # TODO(ewiseblatt): 20150521
    # This doesnt seem to take effect. The intent here is to not sort the order
    # of tests. But it still is. So I've renamed the tests to lexographically
    # sort in place. Leaving this around anyway in hopes to eventually figure
    # out why it doesnt work.
    loader.sortTestMethodsUsing = None

    # NOTE(ewiseblatt):
    # Instead of using this loader, perhaps I could create a suite from a
    # Scenario and then run that. So the scenario would contain a list of
    # OperationTestCase factories (the functions) and then use the results
    # to drive the test case. That might be overkill so stick with standards.
    return loader.loadTestsFromTestCase(cls)

  @classmethod
  def setupScenario(cls, scenarioClass):
    """Setup this integration test class by binding a scenario.

    Args:
      scenarioClass: A class derived from BaseTestScenario that is used to
         create the scenario for instances of this class.
    """
    parser = argparse.ArgumentParser()
    cls.initArgumentParser(parser)
    scenarioClass.initArgumentParser(parser)
    args_namespace = parser.parse_args()
    bindings = args_util.parser_args_to_bindings(args_namespace)

    cls.startLogging(bindings)
    cls.startReportScribe(bindings)
    cls._scenario = cls.make_scenario(
      scenarioClass=scenarioClass, bindings=bindings)

  @classmethod
  def teardownScenario(cls, scenarioClass):
    cls.finishReportScribe()

  @classmethod
  def main(cls, scenarioClass=BaseTestScenario):
    cls.setupScenario(scenarioClass)

    try:
      # Create some separation in logs
      logger = logging.getLogger(__name__)
      logger.info('Finished Setup. Start Tests\n'
                  + ' ' * (8 + 1)  # for leading timestamp prefix
                  + '---------------------------\n')

      suite = cls.buildSuite()
      result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
      if sys.exc_info()[0] != None:
        sys.stderr.write('Tearing down scenario early due to an exception\n')
      cls.teardownScenario(scenarioClass)

    return len(result.failures) + len(result.errors)
