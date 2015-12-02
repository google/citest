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

"""Implements ScenarioTestRunner.

A ScenarioTestRunner is a TestRunner that also manages an AgentScenario to
be shared among all the tests.

Note that the AgentScenario could be factored out to a base Scenario if needed.
"""


import logging

from ..base import TestRunner


# NOTE(ewiseblatt):
# Perhaps instead of a standard test loader, this could create a suite from
# a scenario then run that.  The scenario would contain a list of
# OperationTestCase factories (the functions) and then use the results
# to drive the test case. That might be overkill so stick with standards.
class ScenarioTestRunner(TestRunner):
  """Specialization of citest base.TestRunner to execute AgentTestScenario.

  Instances of this class establish themselves as the global runner,
  which is used to get the AgentTestScenario being run.
  """
  __global_scenario_runner = None

  @property
  def scenario(self):
    """The scenario being run."""
    return self.__scenario

  @staticmethod
  def global_runner():
    """Returns the global instance, which is the last instance created."""
    if ScenarioTestRunner.__global_scenario_runner is None:
      raise BaseException('ScenarioTestRunner not yet instantiated')
    return ScenarioTestRunner.__global_scenario_runner

  @classmethod
  def main(cls, scenario_class,
           runner=None, default_binding_overrides=None, test_case_list=None):
    scenario_runner = cls(scenario_class, runner=runner)
    scenario_runner.set_default_binding_overrides(default_binding_overrides)
    return scenario_runner._do_main(test_case_list=test_case_list)

  def __init__(self, scenario_class, runner=None):
    """Constructs instance.

    scenario_class: [class AgentTestScenario] The scenario that we are going
        to run.
    runner: [unittest.TestRunner] Optional runner to delegate to when running
        the actual TestCases.
    """
    ScenarioTestRunner.__global_scenario_runner = self
    super(ScenarioTestRunner, self).__init__(runner=runner)
    self.__scenario_class = scenario_class
    self.__scenario = None

  def initArgumentParser(self, parser, defaults=None):
    super(ScenarioTestRunner, self).initArgumentParser(
        parser, defaults=defaults)
    self.__scenario_class.initArgumentParser(parser, defaults=defaults)

  def new_scenario(self, scenario_class):
    """Instantiates scenario_class with this instance bindings.

    Args:
      scenario_class: [class AgentTestScenario] To instantiate.
    """
    return scenario_class(self.bindings)

  def _prepare(self):
    """Specialization of base.TestRunner _prepare() prepares the scenario."""
    if self.__scenario:
      raise ValueError('prepare was already called.')
    super(ScenarioTestRunner, self)._prepare()

    logger = logging.getLogger(__name__)
    logger.info('Preparing scenario')
    self.__scenario = self.new_scenario(self.__scenario_class)
