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

# Standard python modules.
import json
import logging
import os
import traceback

# Our modules.
from .. import json_contract as jc
from ..json_predicate import JsonError
from ..service_testing import cli_agent

class GoogleCloudStorageObserver(jc.ObjectObserver):
  """Observe Google Cloud Storage resources."""

  def __init__(self, method, args):
    """Construct observer.

    Args:
      method: The method to invoke.
      args: Command-line argument list to execute.
    """
    super(GoogleCloudStorageObserver, self).__init__()
    self.__method = method
    self.__args = args

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(entity, 'Args', self.__args)
    super(GoogleCloudStorageObserver, self).export_to_json_snapshot(
        snapshot, entity)

  def __str__(self):
    return 'GoogleCloudStorageObserver({0})'.format(self.__args)

  def collect_observation(self, observation, trace=True):
    gsutil_response = self.__method(**self.__args)
    if not gsutil_response.ok():
      observation.add_error(
          cli_agent.CliAgentRunError(self.__method.im_self, gsutil_response))
      return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(gsutil_response.output)
      if not isinstance(doc, list):
        doc = [doc]
      observation.add_all_objects(doc)
    except ValueError as vex:
      error = 'Invalid JSON in response: %s' % str(gsutil_response)
      logging.getLogger(__name__).info('%s\n%s\n----------------\n',
                                       error, traceback.format_exc())
      observation.add_error(JsonError(error, vex))
      return []

    return observation.objects


class GoogleCloudStorageObjectFactory(object):
  """Creates GoogleCloudStorageObserver instances."""

  def __init__(self, gsutil):
    self.__gsutil = gsutil

  def new_list(self, bucket, path, with_versions=False):
    """Create an observer to list the bucket contents at a given path.

    Args:
      bucket: [string] The name of the bucket to list.
      path: [string] The path within the bucket.
      with_versions: [boolean] If False then just latest version,
          otherwise return all versions of all files.

    Returns:
      An observer that will retrieve the specified objects.
    """
    return GoogleCloudStorageObserver(
        self.__gsutil.list,
        {'bucket':bucket, 'path':path, 'with_versions':with_versions})

  def new_retrieve(self, bucket, path):
    """Create an observer to retrieve the contents from a given path.

    Args:
      bucket: [string] The name of the bucket to list.
      path: [string] The path within the bucket.

    Returns:
      An observer that will retrieve the specified content.
    """
    return GoogleCloudStorageObserver(
        self.__gsutil.retrieve, args={'bucket':bucket, 'path':path})


class GoogleCloudStorageClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing GCE state."""

  def __init__(self, title, gsutil, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      gsutil: The GsutilAgent to make the observation for the clause to verify.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
    """
    super(GoogleCloudStorageClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__factory = GoogleCloudStorageObjectFactory(gsutil)
    self.__strict = strict

  def list(self, bucket, path, with_versions=False):
    """List the bucket contents at a given path.

    Args:
      bucket: [string] The name of the bucket to list.
      path: [string] The path within the bucket.
      with_versions: [boolean] If False then just latest version,
          otherwise return all versions of all files.
    """
    self.observer = self.__factory.new_list(bucket, path, with_versions)
    title = ('List ' + ('Versioned ' if with_versions else '')
             + os.path.join(bucket, path))
    observation_builder = jc.ValueObservationVerifierBuilder(
        title, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)

    return observation_builder

  def retrieve(self, bucket, path, no_resource_ok=False):
    """Retrieve actual contents of file at path.

    Args:
      bucket: [string] The gcs bucket containing the path.
      path: [string] The path within the gcs bucket to retreive.
      no_resource_ok: [bool] True if a 404/resource not found is ok.
    """
    self.observer = self.__factory.new_retrieve(bucket, path)

    if no_resource_ok:
      # Construct rule "error_verifier OR <user supplied specification>"
      # where the <user supplied specification> will be returned as our
      # result so that the caller can populate the criteria.
      # We'll append the outer disjunction (disjunction builder) to our
      # verifiers and return the user clause (retrieve_builder) within
      # that disjunction so that the caller can finish specifying it.
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='404 Permitted',
          error_regex='.*(?:does not exist)|(?:matched no objects).*')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Retrieve {0} bucket={1} path={2} or 404'.format(type, bucket, path))
      disjunction_builder.append_verifier(error_verifier)

      retrieve_builder = jc.ValueObservationVerifierBuilder(
          'Retrieve {0} bucket={1} path={2}'.format(type, bucket, path),
          strict=self.__strict)
      disjunction_builder.append_verifier_builder(
          retrieve_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      # Construct the rule <user supplied specification>
      # Here we return the user supplied specification clause as before.
      # But we dont need the outer disjunction, so we also add it directly
      # as the verifier.
      retrieve_builder = jc.ValueObservationVerifierBuilder(
          'Retrieve bucket={0} path={1}'.format(bucket, path),
          strict=self.__strict)
      self.verifier_builder.append_verifier_builder(retrieve_builder)

    return retrieve_builder


class GoogleCloudStorageContractBuilder(jc.ContractBuilder):
  """Specialized contract that facilitates observing Google Cloud Storage."""

  def __init__(self, gsutil):
    """Constructs a new contract.

    Args:
      gsutil: The GsutilAgent to use for communicating with GCS
    """
    super(GoogleCloudStorageContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        GoogleCloudStorageClauseBuilder(
            title, gsutil=gsutil,
            retryable_for_secs=retryable_for_secs, strict=strict))
