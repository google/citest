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


from gcloud_agent import GCloudAgent
from gce_contract import GceContractBuilder # DEPRECATED
from google_cloud_storage_agent import GcpStorageAgent
from google_cloud_storage_contract import GcpStorageContractBuilder
from quota_predicate import (
    QuotaPredicate,
    make_quota_contract,
    verify_quota)

from gcp_agent import (
    GcpAgent,
)

from gcp_contract import GcpContractBuilder

from gcp_error_predicates import (
    GoogleAgentObservationFailureVerifier,
    HttpErrorPredicate,
    HttpErrorPredicateResult,
    )
