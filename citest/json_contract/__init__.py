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


# This module is intended to support the higher level json_contract.* modules.
# To that end, the lookups populate PredicateResult objects rather than just
# returning values, so are heavier weight that would be otherwise.

# The observer module contains support for specifying observers and making
# observations onto a system to collect the data supporting verification.
from observer import (
    ObjectObserver,
    Observation)


# The verifier module provides support for verifying observations meet
# expectations.
from observation_verifier import (
    ObservationVerifier,
    ObservationVerifierBuilder,
    ObservationVerifyResultBuilder,
    ObservationVerifyResult)


from value_observation_verifier import (
    ValueObservationVerifier,
    ValueObservationVerifierBuilder)


from observation_failure import (
    ObservationFailedError,
    ObservationFailureVerifier)


# The contract module provides a means to specify and verify contracts on
# expected system state, and how to collect that state using observations.
from contract import (
    Contract,
    ContractBuilder,
    ContractVerifyResult,
    ContractClause,
    ContractClauseBuilder,
    ContractClauseVerifyResult)
