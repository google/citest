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


"""Provides a means for specifying and verifying expectations of Kubernetes."""

# Standard python modules.
import json
import logging
import traceback

# Our modules.
import citest.json_predicate as jp
import citest.json_contract as jc
import citest.service_testing.cli_agent as cli_agent

class KubeObjectObserver(jc.ObjectObserver):
  """Observe Kubernetes resources."""

  def __init__(self, kubectl, args, filter=None):
    """Construct observer.

    Args:
      kubectl: KubeCtlAgent instance to use.
      args: Command-line argument list to execute.
    """
    super(KubeObjectObserver, self).__init__(filter)
    self.__kubectl = kubectl
    self.__args = args

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Args', self.__args)
    super(KubeObjectObserver, self).export_to_json_snapshot(snapshot, entity)

  def __str__(self):
    return 'KubeObjectObserver({0})'.format(self.__args)

  def collect_observation(self, context, observation):
    args = context.eval(self.__args)
    kube_response = self.__kubectl.run(args)
    if not kube_response.ok():
      observation.add_error(
          cli_agent.CliAgentRunError(self.__kubectl, kube_response))
      return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(kube_response.output)
      if not isinstance(doc, list):
        doc = [doc]
      self.filter_all_objects_to_observation(context, doc, observation)
    except ValueError as vex:
      error = 'Invalid JSON in response: %s' % str(kube_response)
      logging.getLogger(__name__).info('%s\n%s\n----------------\n',
                                       error, traceback.format_exc())
      observation.add_error(jp.JsonError(error, vex))
      return []

    return observation.objects


class KubeObjectFactory(object):
  # pylint: disable=too-few-public-methods

  def __init__(self, kubectl):
    self.__kubectl = kubectl

  def new_get_resources(self, type, extra_args=None):
    """Specify a resource list to be returned later.

    Args:
      type: kubectl's name for the Kubernetes resource type.

    Returns:
      A jc.ObjectObserver to return the specified resource list when called.
    """
    if extra_args is None:
      extra_args = []

    cmd = self.__kubectl.build_kubectl_command_args(
        action='get', resource=type, args=['--output=json'] + extra_args)
    return KubeObjectObserver(self.__kubectl, cmd)


class KubeClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing Kubernetes state."""

  def __init__(self, title, kubectl, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      kubectl: The KubeCtlAgent to make the observation for the clause to
         verify.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
      strict: DEPRECATED flag indicating whether the clauses (added later)
         must be true for all objects (strict) or at least one (not strict).
         See ValueObservationVerifierBuilder for more information.
         This is deprecated because in the future this should be on a per
         constraint basis.
    """
    super(KubeClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__factory = KubeObjectFactory(kubectl)
    self.__strict = strict

  def get_resources(self, type, extra_args=None, no_resource_ok=False):
    """Observe resources of a particular type.

    This ultimately calls a "kubectl ... get |type| |extra_args|"

    Args:
      no_resource_ok: Whether or not the resource is required.
          If the resource is not required, "not found" is treated as a valid
          check. Because resource deletion is asynchronous, there is no
          explicit API here to confirm that a resource does not exist.
    """
    self.observer = self.__factory.new_get_resources(
        type, extra_args=extra_args)

    if no_resource_ok:
      # Unfortunately gcloud does not surface the actual 404 but prints an
      # error message saying that it was not found.
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='Not Found Permitted', error_regex='.* not found')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Get {0} {1} or Not Found'.format(type, extra_args))
      disjunction_builder.append_verifier(error_verifier)

      get_builder = jc.ValueObservationVerifierBuilder(
          'Get {0} {1}'.format(type, extra_args), strict=self.__strict)
      disjunction_builder.append_verifier_builder(
          get_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      get_builder = jc.ValueObservationVerifierBuilder(
          'Get {0} {1}'.format(type, extra_args), strict=self.__strict)
      self.verifier_builder.append_verifier_builder(get_builder)

    return get_builder


class KubeContractBuilder(jc.ContractBuilder):
  """Specialized contract that facilitates observing Kubernetes."""

  def __init__(self, kubectl):
    """Constructs a new contract.

    Args:
      kubectl: The KubeCtlAgent to use for communicating with Kubernetes.
    """
    super(KubeContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        KubeClauseBuilder(
            title, kubectl=kubectl,
            retryable_for_secs=retryable_for_secs, strict=strict))
