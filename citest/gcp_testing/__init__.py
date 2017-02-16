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


"""Citest support modules for testing against Google Cloud Platform (GCP)."""


from gcp_agent import GcpAgent
from gcp_contract import GcpContractBuilder

from gcp_compute_agent import (
    COMPUTE_FULL_SCOPE,
    COMPUTE_READ_ONLY_SCOPE,
    COMPUTE_READ_WRITE_SCOPE,
    GcpComputeAgent)
    
from gcp_storage_agent import (
    GcpStorageAgent,
    STORAGE_FULL_SCOPE,
    STORAGE_READ_ONLY_SCOPE,
    STORAGE_READ_WRITE_SCOPE)
    
from gcp_storage_contract import GcpStorageContractBuilder

from gcloud_agent import GCloudAgent
from gcloud_contract import GCloudContractBuilder

from quota_predicate import (
    QuotaPredicate,
    make_quota_contract,
    verify_quota)

from gcp_error_predicates import (
    GoogleAgentObservationFailureVerifier,
    HttpErrorPredicate,
    HttpErrorPredicateResult,
    )

from gcp_appengine_agent import (
    APPENGINE_FULL_SCOPE,
    APPENGINE_READ_ONLY_SCOPE,
    APPENGINE_READ_WRITE_SCOPE,
    GcpAppengineAgent)
