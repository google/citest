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


# The testable_agent module contains the base definitions.
from testable_agent import(
    AgentError,
    AgentOperation,
    AgentOperationStatus,
    TestableAgent)


# The cli_agent module implements an agent that uses command-line programs.
from cli_agent import (
    CliAgent,
    CliAgentObservationFailureVerifier,
    CliAgentRunError,
    CliResponseType,
    CliRunOperation,
    CliRunStatus)


# The cli_agent module implements an agent that uses HTTP messaging.
from http_agent import (
    HttpAgent,
    HttpOperationStatus,
    HttpPostOperation,
    HttpResponseType)

from http_observer import (
    HttpObjectObserver,
    HttpContractBuilder,
    HttpContractClauseBuilder,
    )

# The operation_contract module combines AgentOperation and JsonContract.
from operation_contract import OperationContract


# The service_testing module adds support for writing tests around TestableAgent
from agent_test_case import (
    AgentTestCase,
    AgentTestScenario)

from scenario_test_runner import ScenarioTestRunner
