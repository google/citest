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

# pylint: disable=missing-docstring

import os
import sys
import unittest

from citest.base.bindings import (
    ConfigurationBindingsBuilder)


class TestLazyEvaluator(object):
  """Callable for testing lazy initialization.

  Generates values and keeps track of call sequence.
  Contains a special key "implied" that "lazy" key depends on to test
  evaluators with side effects.
  """

  def __init__(self):
    self.called_with_bk = []  # tuple of (bindings, key)

  def __call__(self, bindings, key):
    if key == 'lazy':
      if bindings.get('implied'):
        pass  # Forcing side-effect initialization of another key.

    self.called_with_bk.append((bindings, key))
    return len(self.called_with_bk)


class ConfigurationBindingsTest(unittest.TestCase):
  def test_not_found(self):
    bindings = ConfigurationBindingsBuilder().build()
    self.assertIsNone(bindings.get('missing'))
    with self.assertRaises(KeyError):
      self.assertIsNotNone(bindings['missing'])

  def test_just_default(self):
    builder = ConfigurationBindingsBuilder()
    builder.set_default('test', 'MyDefault')
    bindings = builder.build()
    self.assertEquals('MyDefault', bindings.get('test'))

  def test_just_override(self):
    builder = ConfigurationBindingsBuilder()
    builder.set_override('test', 'MyOverride')
    bindings = builder.build()
    self.assertEquals('MyOverride', bindings.get('test'))

  def test_case_insensitive_override(self):
    builder = ConfigurationBindingsBuilder()
    builder.set_override('test', 'MyOverride')
    bindings = builder.build()
    self.assertEquals('MyOverride', bindings.get('TEST'))

  def test_override_default(self):
    builder = ConfigurationBindingsBuilder()
    builder.set_default('test', 'MyPreDefault')
    builder.set_override('test', 'MyOverride')
    builder.set_default('test', 'MyPostDefault')

    bindings = builder.build()
    self.assertEquals('MyOverride', bindings.get('test'))

  def test_from_file(self):
    builder = ConfigurationBindingsBuilder()
    builder.add_config_file(os.path.join(os.path.dirname(__file__),
                                         'bindings_test.config'))
    bindings = builder.build()
    self.assertEquals('tests/base/bindings_test',
                      bindings.get('config_location'))

  def test_from_file_for_class(self):
    builder = ConfigurationBindingsBuilder()
    builder.add_configs_for_class(ConfigurationBindingsTest)
    bindings = builder.build()
    self.assertEquals('tests/base/ConfigurationBindingsTest',
                      bindings.get('config_location'))
    self.assertIsNone(bindings.get('missing'))

  def test_from_file_for_class_with_defaults(self):
    builder = ConfigurationBindingsBuilder()
    builder.add_configs_for_class(ConfigurationBindingsTest)
    builder.set_default('missing', 'MISSING')
    builder.set_default('config_location', 'IGNORE')
    bindings = builder.build()
    self.assertEquals('MISSING', bindings.get('missing'))
    self.assertEquals('tests/base/ConfigurationBindingsTest',
                      bindings.get('config_location'))

  def test_from_command_line(self):
    orig_argv = sys.argv
    try:
      sys.argv = [orig_argv[0],
                  '--config_location=COMMANDLINE',
                  '--overriden=WRONG',
                  '--unknownBool',
                  '--unknownInt', '123']

      builder = ConfigurationBindingsBuilder()
      builder.add_configs_for_class(ConfigurationBindingsTest)
      builder.set_override('overriden', 'OVERRIDEN')
      bindings = builder.build()
      self.assertEquals('OVERRIDEN', bindings.get('overriden'))
      self.assertEquals('COMMANDLINE',
                        bindings.get('config_location'))
      self.assertEquals('True', bindings.get('unknownBool'))
      self.assertEquals('123', bindings.get('unknownInt'))
      self.assertIsNone(bindings.get('missing'))
    finally:
      sys.argv = orig_argv

  def test_lazy_initializer(self):
    lazy_evaluator = TestLazyEvaluator()
    builder = ConfigurationBindingsBuilder()
    builder.add_lazy_initializer('lazy', lazy_evaluator)
    builder.add_lazy_initializer('implied', lazy_evaluator)
    builder.add_lazy_initializer('overriden', lazy_evaluator)
    builder.add_lazy_initializer('has_default', lazy_evaluator)
    builder.set_default('has_default', 'default')

    bindings = builder.build()
    self.assertEqual(2, bindings['lazy'])
    self.assertEqual(1, bindings['IMPLIED'])  # already initialized

    bindings['overriden'] = 'Hello'
    self.assertEquals('Hello', bindings['overriden'])

    # Default is lower precedence than lazy initializer
    self.assertEquals(3, bindings['has_default'])

    with self.assertRaises(KeyError):
      self.assertIsNotNone(bindings['missing'])

    self.assertEquals([(bindings, 'implied'),
                       (bindings, 'lazy'),
                       (bindings, 'has_default')],
                      lazy_evaluator.called_with_bk)

  def test_lazy_overrides_removes_None_override(self):
    lazy_evaluator = TestLazyEvaluator()

    builder = ConfigurationBindingsBuilder()
    builder.set_override('overriden', None)
    builder.set_override('has_default', 'have')
    builder.add_lazy_initializer('overriden', lazy_evaluator)
    builder.add_lazy_initializer('has_default', lazy_evaluator)
    builder.add_lazy_initializer('lazy', lazy_evaluator)
    builder.set_override('lazy', None)

    bindings = builder.build()
    self.assertEquals(1, bindings.get('overriden'))
    self.assertEquals('have', bindings.get('has_default'))
    self.assertIsNone(bindings.get('lazy')) # because we overrode it

  def test_contains(self):
    lazy_evaluator = TestLazyEvaluator()
    builder = ConfigurationBindingsBuilder()
    builder.add_lazy_initializer('lazy', lazy_evaluator)
    builder.add_lazy_initializer('shared', lazy_evaluator)
    builder.add_configs_for_class(ConfigurationBindingsTest)
    builder.set_override('shared', 'OverridenValue')
    builder.set_override('overriden', 'OverridenValue')
    builder.set_default('default', 'DefaultValue')

    bindings = builder.build()
    self.assertTrue('lazy' in bindings)
    self.assertTrue('shared' in bindings)
    self.assertTrue('overriden' in bindings)
    self.assertTrue('default' in bindings)
    self.assertTrue('DeFaUlT' in bindings)
    self.assertTrue('read_configuration_bindings_test' in bindings)
    self.assertTrue('tests_base_param' in bindings)

    self.assertFalse('missing' in bindings)

    self.assertEquals([], lazy_evaluator.called_with_bk)
    self.assertFalse('implied' in bindings)


if __name__ == '__main__':
  unittest.main()
