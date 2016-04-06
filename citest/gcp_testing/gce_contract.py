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


"""Provides a means for specifying and verifying expectations of GCE state."""

# Standard python modules.
import json
import logging
import traceback

# Our modules.
from .. import json_contract as jc
from ..json_predicate import JsonError
from ..service_testing import cli_agent

class GCloudObjectObserver(jc.ObjectObserver):
  """Observe GCP resources."""

  def __init__(self, gcloud, args, filter=None):
    """Construct observer.

    Args:
      gcloud: GCloudAgent instance to use.
      args: Command-line argument list to execute.
    """
    super(GCloudObjectObserver, self).__init__(filter)
    self.__gcloud = gcloud
    self.__args = args

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(entity, 'Args', self.__args)
    super(GCloudObjectObserver, self).export_to_json_snapshot(snapshot, entity)

  def __str__(self):
    return 'GCloudObjectObserver({0})'.format(self.__args)

  def collect_observation(self, observation, trace=True):
    gcloud_response = self.__gcloud.run(self.__args, trace=trace)
    if not gcloud_response.ok():
      observation.add_error(
          cli_agent.CliAgentRunError(self.__gcloud, gcloud_response))
      return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(gcloud_response.output)
      if not isinstance(doc, list):
        doc = [doc]
      observation.add_all_objects(doc)
    except ValueError as vex:
      error = 'Invalid JSON in response: %s' % str(gcloud_response)
      logging.getLogger(__name__).info('%s\n%s\n----------------\n',
                                       error, traceback.format_exc())
      observation.add_error(JsonError(error, vex))
      return []

    return observation.objects


class GCloudObjectFactory(object):

  def __init__(self, gcloud):
    self.__gcloud = gcloud

  def new_list_resources(self, type, extra_args=None):
    """Specify a resource list to be returned later.

    Args:
      type: gcloud's name for the GCE resource type.

    Returns:
      A jc.ObjectObserver to return the specified resource list when called.
    """
    zone = None
    if extra_args is None:
      extra_args = []
    if self.__gcloud.command_needs_zone(type, 'list'):
      zone = self.__gcloud.zone
      # But if we already had it, dont add it.
      try:
        if extra_args.index('--zone') >= 0:
          zone = None
      except ValueError:
        pass

    cmd = self.__gcloud.build_gcloud_command_args(
        type, ['list'] + extra_args, project=self.__gcloud.project, zone=zone)
    return GCloudObjectObserver(self.__gcloud, cmd)

  def new_inspect_resource(self, type, name, extra_args=None):
    """Specify a resource instance to inspect later.

    Args:
      type: gcloud's name for the GCE resource type.
      name: The name of the specific resource instance to inspect.

    Returns:
      An jc.ObjectObserver to return the specified resource details when called.
    """
    zone = None
    if extra_args is None:
      extra_args = []

    if self.__gcloud.command_needs_zone(type, 'describe'):
      zone = self.__gcloud.zone
      try:
        if extra_args.index('--zone') >= 0:
          zone = None
      except ValueError:
        pass

    cmd = self.__gcloud.build_gcloud_command_args(
        type, ['describe', name] + extra_args,
        project=self.__gcloud.project, zone=zone)
    return GCloudObjectObserver(self.__gcloud, cmd)


class GCloudClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing GCE state."""

  def __init__(self, title, gcloud, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      gcloud: The GCloudAgent to make the observation for the clause to verify.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
      strict: DEPRECATED flag indicating whether the clauses (added later)
         must be true for all objects (strict) or at least one (not strict).
         See ValueObservationVerifierBuilder for more information.
         This is deprecated because in the future this should be on a per
         constraint basis.
    """
    super(GCloudClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__factory = GCloudObjectFactory(gcloud)
    self.__strict = strict

  def list_resources(self, type, extra_args=None):
    """Observe resources of a particular type.

    This ultimately calls a "gcloud ... |type| list |extra_args|"
    """
    self.observer = self.__factory.new_list_resources(type, extra_args)
    observation_builder = jc.ValueObservationVerifierBuilder(
        'List ' + type, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)

    return observation_builder

  def inspect_resource(self, type, name, extra_args=None, no_resource_ok=False):
    """Observe the details of a specific instance.

    This ultimately calls a "gcloud ... |type| |name| describe |extra_args|"

    Args:
      type: The gcloud resource type  (e.g. instances)
      name: The GCE resource name
      extra_args: Additional parameters to pass to gcloud.
      no_resource_ok: Whether or not the resource is required.
          If the resource is not required, a 404 is treated as a valid check.
          Because resource deletion is asynchronous, there is no explicit
          API here to confirm that a resource does not exist.

    Returns:
      A js.ValueObservationVerifier that will collect the requested resource
          when its verify() method is run.
    """

    self.observer = self.__factory.new_inspect_resource(type, name, extra_args)

    if no_resource_ok:
      # Unfortunately gcloud does not surface the actual 404 but prints an
      # error message saying that it was not found.
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='404 Permitted', error_regex='.* was not found.*')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Inspect {0} {1} or 404'.format(type, name))
      disjunction_builder.append_verifier(error_verifier)

      inspect_builder = jc.ValueObservationVerifierBuilder(
          'Inspect {0} {1}'.format(type, name), strict=self.__strict)
      disjunction_builder.append_verifier_builder(
          inspect_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      inspect_builder = jc.ValueObservationVerifierBuilder(
          'Inspect {0} {1}'.format(type, name), strict=self.__strict)
      self.verifier_builder.append_verifier_builder(inspect_builder)

    return inspect_builder


class GceContractBuilder(jc.ContractBuilder):
  """Specialized contract that facilitates observing GCE."""

  def __init__(self, gcloud):
    """Constructs a new contract.

    Args:
      gcloud: The GCloudAgent to use for communicating with GCE.
    """
    super(GceContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        GCloudClauseBuilder(
            title, gcloud=gcloud,
            retryable_for_secs=retryable_for_secs, strict=strict))
