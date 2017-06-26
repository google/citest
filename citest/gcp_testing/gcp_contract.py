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
import logging
import traceback

from googleapiclient.errors import HttpError

# Our modules.
from .. import json_contract as jc


class GcpObjectObserver(jc.ObjectObserver):
  """Observe GCP resources."""

  def __init__(self, method, filter=None, **kwargs):
    """Construct observer.

    Args:
      gcp_agent: GcpAgent instance to use.
      method: [method] The method to invoke.
      kwargs: [kwargs] arguments to pass to method.
    """
    super(GcpObjectObserver, self).__init__(filter)

    self.__method = method
    self.__kwargs = dict(kwargs)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Args', self.__kwargs)
    super(GcpObjectObserver, self).export_to_json_snapshot(snapshot, entity)

  def __str__(self):
    return 'GcpObjectObserver({0})'.format(self.__kwargs)

  def collect_observation(self, context, observation, trace=True):
    try:
      doc = self.__method(context, **self.__kwargs)
      if not isinstance(doc, list):
        doc = [doc]
      self.filter_all_objects_to_observation(context, doc, observation)
    except HttpError as http_error:
      logging.getLogger(__name__).info('%s\n%s\n----------------\n',
                                       http_error, traceback.format_exc())
      observation.add_error(http_error)
      return []

    return observation.objects


class GcpClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing GCE state."""

  @property
  def gcp_agent(self):
    """Returns the bound GcpAgent performing the observations."""
    return self.__gcp_agent

  def __init__(self, title, gcp_agent, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      gcp_agent: The GcpAgent to make the observation for the clause to verify.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
      strict: DEPRECATED flag indicating whether the clauses (added later)
         must be true for all objects (strict) or at least one (not strict).
         See ValueObservationVerifierBuilder for more information.
         This is deprecated because in the future this should be on a per
         constraint basis.
    """
    super(GcpClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__gcp_agent = gcp_agent
    self.__strict = strict

  def list_resource(self, resource_type, **kwargs):
    """Observe resources of a particular type."""
    self.observer = GcpObjectObserver(
        self.__gcp_agent.list_resource, resource_type=resource_type, **kwargs)
    observation_builder = jc.ValueObservationVerifierBuilder(
        'List ' + resource_type, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)

    return observation_builder

  def aggregated_list_resource(self, resource_type, **kwargs):
    """Observe resources of a particular type."""
    self.observer = GcpObjectObserver(
        self.__gcp_agent.aggregated_list_resource, resource_type=resource_type,
        **kwargs)
    observation_builder = jc.ValueObservationVerifierBuilder(
        'List Aggregated ' + resource_type, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)

    return observation_builder

  def inspect_resource(self, resource_type, resource_id,
                       **kwargs):
    """Observe the details of a specific instance.

    Args:
      resource_type: The gcp resource type  (e.g. instances)
      resource_id: The GCP |resource| instance id
      no_resource_ok: Whether or not the resource is required.
          If the resource is not required, a 404 is treated as a valid check.
          Because resource deletion is asynchronous, there is no explicit
          API here to confirm that a resource does not exist.
      kwargs: Additional parameters to pass to gcp_agent

    Returns:
      A js.ValueObservationVerifier that will collect the requested resource
          when its verify() method is run.
    """
    if 'no_resource_ok' in kwargs:
      raise KeyError('no_resource_ok was DEPRECATED and removed.')

    self.observer = GcpObjectObserver(
        self.__gcp_agent.get_resource,
        resource_type=resource_type,
        resource_id=resource_id,
        **kwargs)

    inspect_builder = jc.ValueObservationVerifierBuilder(
        'Inspect {0} {1}'.format(resource_type, resource_id),
        strict=self.__strict)
    self.verifier_builder.append_verifier_builder(inspect_builder)

    return inspect_builder


class GcpContractBuilder(jc.ContractBuilder):
  """Specialized contract that facilitates observing GCE."""

  def __init__(self, gcp_agent, clause_factory=None):
    """Constructs a new contract.

    Args:
      gcp_agent: [GcpAgent] The GcpAgent to use for communicating with GCE.
      clause_factory: [factory creating a ContractClauseBuilder]
    """
    if clause_factory is None:
      clause_factory = (
          lambda title, retryable_for_secs=0, strict=False:
              GcpClauseBuilder(title, gcp_agent=gcp_agent,
                               retryable_for_secs=retryable_for_secs,
                               strict=strict))
    super(GcpContractBuilder, self).__init__(clause_factory)
