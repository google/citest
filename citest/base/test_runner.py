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

There is an experimental feature in which an environment variable
CITEST_CONFIG_PATH can point to a config file with the default config
parameters to use. This is likely to change or be removed in the future
so is not advised to rely on it at this time.
"""

# Standard python modules.
import ast
import logging
import logging.config
import os
import os.path
import stat
import sys
import unittest

# Our modules.
from . import global_journal
from . import args_util
from .bindings import ConfigurationBindingsBuilder
from .snapshot import JsonSnapshotableEntity

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
     'filename':'$LOG_DIR/$LOG_FILEBASE.log',
     'mode':'w'
   },
   'journal':{
     'level':'DEBUG',
     'class':'citest.base.JournalLogHandler',
     'path' : '$LOG_DIR/$LOG_FILEBASE.journal'
   }
  },
  'loggers':{
    '': {
      'level':'DEBUG',
      'handlers':['console', 'file', 'journal']
    },
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
  __singleton_scenario_instances = {}

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

  @staticmethod
  def get_shared_data(klass):
    """Get the shared instance of a given class.

    This assumes klass has a constructor that takes a bindings dictionary
    with configuration default overrides. It will create the instance
    on the first call, and return the shared instance thereafter.

    This is intended to allow different tests to share common data where
    each test is run by an independent TestCase instance but share the
    underlying data object returned by this method.
    """
    if not klass in TestRunner.__singleton_scenario_instances:
      global_runner = TestRunner.global_runner()
      bindings = global_runner.bindings
      if hasattr(klass, 'init_bindings_builder'):
        builder = ConfigurationBindingsBuilder()
        builder.add_configs_for_class(klass)
        klass.init_bindings_builder(builder, defaults=bindings)
        bindings = builder.build()

      instance = klass(bindings)
      TestRunner.__singleton_scenario_instances[klass] = instance
      return instance
    return TestRunner.__singleton_scenario_instances[klass]

  @classmethod
  def main(cls, runner=None,
           config_files=None,
           parser_inits=None,
           default_binding_overrides=None,
           test_case_list=None):
    """Implements a main method for running tests.

    This main will instantiate an instance of the class |cls| then
    pass control to the _do_main method on the instantiated runner.

    Args:
      runner: If provided, then delegate to this runner to run the tests.
      config_files: A list of config files to load options from.
      parser_inits: A list of functions (argumentParser, defaults=defaultDict)
          for initializing the argumentParser with custom arguments using
          optional default values for each argument.
      default_binding_overrides: Provides a means to inject default values
          to use for bindings.
      test_case_list: If provided, a list of test cases to run.
    """
    explicit_parser_inits = set(parser_inits or [])
    implicit_parser_inits = set([])
    for klass in test_case_list or []:
      if hasattr(klass, 'init_bindings_builder'):
        implicit_parser_inits.add(klass.init_bindings_builder)

    runner = cls(runner=runner)
    runner.set_default_binding_overrides(default_binding_overrides)
    runner.set_parser_inits(
        list(explicit_parser_inits.union(implicit_parser_inits)))
    runner.set_config_files(config_files)

    # pylint: disable=protected-access
    return runner._do_main(test_case_list=test_case_list)

  def set_default_binding_overrides(self, default_binding_overrides):
    """Provides a means for setting the default_binding_overrides attribute.

    This is intentionally not an assignment because it is not intended to be
    called, but is here in case it is not possible to use the "main()" method.
    """
    self.__default_binding_overrides = default_binding_overrides

  def set_parser_inits(self, inits):
    """Provides a means for setting the parser_inits attribute.

    This is intentionally not an assignment because it is not intended to be
    called, but is here in case it is no possible to use the "main()" method.
    """
    self.__parser_inits = inits or []

  def set_config_files(self, config_files):
    """Provides a means for setting the config_files attribute.

    This is intentionally not an assignment because it is not intended to be
    called, but is here in case it is no possible to use the "main()" method.
    """
    self.__config_files = config_files or []

  def _do_main(self, default_binding_overrides=None, test_case_list=None):
    """Helper function used by main() once a TestRunner instance exists."""
    # pylint: disable=unused-argument
    # default_binding_overrides is declared as a prototype for derived classes
    # but not actually used here.
    logger = logging.getLogger(__name__)
    logger.info('Building test suite')
    suite = self.build_suite(test_case_list)

    if not self.__parser_inits:
      for test in test_case_list or []:
        self.__bindings_builder.add_configs_for_class(test)
        if hasattr(test, 'init_bindings_builder'):
          self.__parser_inits.append(test.init_bindings_builder)

    # Create some separation in logs
    logger.info('Finished Setup. Start Tests\n'
                + ' ' * (8 + 1)  # for leading timestamp prefix
                + '---------------------------\n')
    result = self.run(suite)

    self._terminate_and_flush_journal()
    return len(result.failures) + len(result.errors)

  def _terminate_and_flush_journal(self):
    """Helper function to supress when testing.

    This function will terminate the journal. However, the journal
    is shared with the logging handler so that both write to the same place.
    When we are testing, we might need to override this so that we can
    test main() among other functions. We dont want to terminate the journal
    because in the bigger picture, we need the logger for the remaining tests.
    """
    logger = logging.getLogger(__name__)
    if self.__journal:
      # Terminate the journal to close and flush the file.
      # Unbind the global journal so it is no longer referencing here.
      if global_journal.get_global_journal() == self.__journal:
        global_journal.unset_global_journal()
      self.__journal.terminate()

      journal_path = os.path.join(
          self.bindings['LOG_DIR'],
          self.bindings['LOG_FILEBASE'] + '.journal')
      # Ideally we just call generate_html_report.main here directly.
      # However, this leads to a circular dependency. So, we'll fork a
      # process for it to decouple the modules when parsing.
      generate_command = ['python',
                          '-m', 'citest.reporting.generate_html_report',
                          '--prune',
                          '--noindex', journal_path]
      logger.info('Running %s', generate_command)
      retcode = os.system(' '.join(generate_command))
      if not retcode:
        sys.stdout.write('Wrote {0}.html\n'.format(
            os.path.splitext(journal_path)[0]))
      else:
        logger.error('Could not write %s.html\n', journal_path)

  def __init__(self, runner=None):
    default_config = os.environ.get('CITEST_CONFIG_PATH')
    TestRunner.__global_runner = self
    self.__delegate = runner or unittest.TextTestRunner(verbosity=2)
    self.__options = None
    self.__bindings = {}
    self.__parser_inits = []
    self.__journal = None
    self.__config_files = []
    self.__default_binding_overrides = {}
    self.__bindings_builder = ConfigurationBindingsBuilder(
        default_config_files=[default_config] if default_config else [])

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
      if sys.exc_info()[0] is not None:
        sys.stderr.write('Terminated early due to an exception\n')
      self._cleanup()

    return result

  def init_bindings_builder(self, builder, defaults=None):
    """Adds configuration introduced by the TestRunner module.

    Args:
      builder: ConfigurationBindingsBuilder instance to add to.
    """
    # Normally we want the log file name to reflect the name of the program
    # we are running, but we might not be running one (e.g. in interpreter).
    try:
      basename = os.path.basename(sys.argv[0])
      main_filename = os.path.splitext(basename)[0]
    except IndexError:
      main_filename = 'debug'

    defaults = (defaults or {})
    builder.add_argument('--log_dir', default=defaults.get('LOG_DIR', '.'))
    builder.add_argument('--log_filebase',
                         default=defaults.get('LOG_FILEBASE', main_filename))
    builder.add_argument(
        '--log_config', default=defaults.get('LOG_CONFIG', ''),
        help='Path to text file containing custom logging configuration. The'
        ' contents of this path can contain variable references in the form'
        ' $KEY where --KEY is a command-line argument that whose value should'
        ' be substituted. Otherwise this is a standard python logging'
        ' configuration schema as described in'
        ' https://docs.python.org/2/library/logging.config.html'
        '#logging-config-dictschema')

  def initArgumentParser(self, parser, defaults=None):
    """Adds arguments introduced by the TestRunner module.

    Args:
      parser: argparse.ArgumentParser instance to add to.
    """
    print('{} called DEPRECATED initArgumentParser\n'
          'Use init_bindings_builder instead.'
          .format(self.__class__.__name__))

    # Normally we want the log file name to reflect the name of the program
    # we are running, but we might not be running one (e.g. in interpreter).
    try:
      basename = os.path.basename(sys.argv[0])
      main_filename = os.path.splitext(basename)[0]
    except IndexError:
      main_filename = 'debug'

    defaults = defaults or {}
    parser.add_argument('--log_dir', default=defaults.get('LOG_DIR', '.'))
    parser.add_argument('--log_filebase',
                        default=defaults.get('LOG_FILEBASE', main_filename))
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
    """Setup default logging from the citest.base.log_config parameter."""
    text = _DEFAULT_LOG_CONFIG
    path = self.bindings.get('LOG_CONFIG', None)
    if path:
      try:
        with open(path, 'r') as f:
          text = f.read()
      except Exception as ex:
        print('ERROR reading LOGGING_CONFIG from {0}: {1}'.format(path, ex))
        raise
    config = ast.literal_eval(args_util.replace(text, self.bindings))
    logging.config.dictConfig(config)
    log_path = os.path.join(
        self.bindings['LOG_DIR'], self.bindings['LOG_FILEBASE'] + '.log')
    os.chmod(log_path, stat.S_IRUSR | stat.S_IWUSR)

    self.__journal = global_journal.get_global_journal()
    if self.__journal is None:
      # force start
      journal_path = os.path.join(
          self.bindings['LOG_DIR'],
          self.bindings['LOG_FILEBASE'] + '.journal')
      self.__journal = global_journal.new_global_journal_with_path(journal_path)

  def report(self, obj):
    """Add object to report.

    Args:
      obj: The object to write into the report.
    """
    if isinstance(obj, JsonSnapshotableEntity):
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
    # The argparse parser is going to set default values that will override
    # the config file. That's not what we want. So grab the config file values
    # as the default values to give to the argparser. The ConfigBindings
    # will handle all the processing and precedence, so create a private one
    # for purposes of passing in "default" values while we initialize the
    # "real" builder we're going to use for the bindings we create.
    default_config = os.environ.get('CITEST_CONFIG_PATH')
    init_defaults = ConfigurationBindingsBuilder(
        default_config_files=[default_config] if default_config else [],
        defaults=self.default_binding_overrides).build()

    for init in self.__parser_inits:
      init(self.__bindings_builder, defaults=init_defaults)

    self.init_bindings_builder(self.__bindings_builder,
                               defaults=init_defaults)
    self.__bindings = self.__bindings_builder.build()
    self.start_logging()

  def _cleanup(self):
    """Helper function when running a suite for cleaning up the global context.
    """
    pass
