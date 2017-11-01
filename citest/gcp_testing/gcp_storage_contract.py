# Copyright 2016 Google Inc. All Rights Reserved.
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


"""Provides a means for specifying and verifying expectations of GCE state."""


# Our modules.
import citest.json_contract as jc
from .gcp_contract import (
    GcpObjectObserver,
    GcpClauseBuilder,
    GcpContractBuilder)

class GcpStorageClauseBuilder(GcpClauseBuilder):
  """A ContractClause that facilitates observing GCE state."""

  def __init__(self, title, gcs_agent, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      gcs_agent: The GcpStorageAgent to make the observation for the clause
          to verify.
      retryable_for_secs: Number of seconds that observations can be retried
          if their verification initially fails.
    """
    super(GcpStorageClauseBuilder, self).__init__(
        title=title, gcp_agent=gcs_agent,
        retryable_for_secs=retryable_for_secs)
    self.__strict = strict

  def list_bucket(self, bucket, path_prefix, with_versions=False, **kwargs):
    """List the bucket contents at a given path.

    Args:
      bucket: [string] The name of the bucket to list.
      path_prefix: [string] The object path prefix within the bucket.
      with_versions: [boolean] If False then just latest version,
          otherwise return all versions of all files.
    """
    self.observer = GcpObjectObserver(
        self.gcp_agent.list_bucket,
        bucket=bucket, path_prefix=path_prefix, with_versions=with_versions,
        **kwargs)
    title = ('List {0} (with_versions={1}, {2})'
             .format('/'.join([bucket, path_prefix]), with_versions, kwargs))
    observation_builder = jc.ValueObservationVerifierBuilder(
        title, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)

    return observation_builder

  def retrieve_content(self, bucket, path, transform=None):
    """Retrieve actual contents of file at path.

    Args:
      bucket: [string] The gcs bucket containing the path.
      path: [string] The path within the gcs bucket to retreive.
      no_resource_ok: [bool] True if a 404/resource not found is ok.
    """
    self.observer = GcpObjectObserver(self.gcp_agent.retrieve_content,
                                      bucket=bucket, path=path,
                                      transform=transform)

    # Construct the rule <user supplied specification>
    # Here we return the user supplied specification clause as before.
    # But we dont need the outer disjunction, so we also add it directly
    # as the verifier.
    retrieve_builder = jc.ValueObservationVerifierBuilder(
        'Retrieve bucket={0} path={1}'.format(bucket, path),
        strict=self.__strict)
    self.verifier_builder.append_verifier_builder(retrieve_builder)

    return retrieve_builder


class GcpStorageContractBuilder(GcpContractBuilder):
  """Specialized contract that facilitates observing Google Cloud Storage."""

  def __init__(self, gcs_agent, clause_factory=None):
    """Constructs a new contract.

    Args:
      gcs_agent: The GcpStorageAgent to use for communicating with GCS
      clause_factory: [factory creating a ContractClauseBuilder]
    """
    if clause_factory is None:
      clause_factory = (
          lambda title, retryable_for_secs=0, strict=False:
              GcpStorageClauseBuilder(title, gcs_agent=gcs_agent,
                                      retryable_for_secs=retryable_for_secs,
                                      strict=strict))

    super(GcpStorageContractBuilder, self).__init__(gcs_agent, clause_factory)
