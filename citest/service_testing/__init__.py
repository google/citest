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

"""This package contains modules for testing services with citest.

The service_testing module provides an adapter for external system interactions
as generic citest operations that can be controlled and reported using
core citest components.

The operation_contract module provides a means for specifying "test cases"
using agent operations to be performed and contracts with observations and
rules to verify their effects.

The http_agent and cli_agent provide concrete base classes for agents
that interact with external systems using either HTTP messaging or
invocation of command-line programs.
"""

# The base_agent module contains the base definitions.
from base_agent import(
    AgentError,
    AgentOperation,
    AgentOperationStatus,
    BaseAgent)


# The cli_agent module implements an agent that uses command-line programs.
from cli_agent import (
    CliAgent,
    CliAgentObservationFailureVerifier,
    CliAgentRunError,
    CliResponseType,
    CliRunOperation,
    CliRunStatus)


# The http_agent module implements an agent that uses HTTP messaging.
from http_agent import (
    HttpAgent,
    HttpDeleteOperation,
    HttpOperationStatus,
    HttpPostOperation,
    HttpResponseType,
    SynchronousHttpOperationStatus)

from http_observer import (
    HttpObjectObserver,
    HttpContractBuilder,
    HttpContractClauseBuilder,
    HttpObservationFailureVerifier,
    )

from http_scrubber import (
    DefaultHttpHeadersScrubber,
    HttpScrubber)

# The operation_contract module combines AgentOperation and JsonContract.
from operation_contract import OperationContract

# A NoOpOperation can be used to create a contract for an invariant.
from nop_operation import NoOpOperation

# The service_testing module adds support for writing tests with BaseAgent.
from agent_test_case import (
    AgentTestCase,
    AgentTestScenario)

