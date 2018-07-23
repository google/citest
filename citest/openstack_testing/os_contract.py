# Copyright 2017 Veritas Technologies, LLC. All Rights Reserved.
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


"""Support for specifying citest.json_contract.Contract
on OpenStack resources."""

import json

import citest.json_contract as jc
from citest.json_predicate import JsonError
import citest.service_testing.cli_agent as cli_agent

class OsObjectObserver(jc.ObjectObserver):
  """Observe OpenStack resources."""

  def __init__(self, agent, args, filter=None):
    """Construct new observer.

    Args:
      agent: OsAgent to observe with.
      args: Command line arguments to pass to openstack program.
      filter: If provided, then use this to filter observations.
    """
    super(OsObjectObserver, self).__init__(filter)
    self.__os = agent
    self.__args = args

  def __str__(self):
    return 'OsObjectObserver({0})'.format(self.__args)

  def collect_observation(self, context, observation):
    args = context.eval(self.__args)
    os_response = self.__os.run(args)
    if not os_response.ok():
      observation.add_error(
          cli_agent.CliAgentRunError(self.__os, os_response))
      return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(os_response.output)
    except (ValueError, UnicodeError) as e:
      error = 'Invalid JSON in response: %s' % str(os_response)
      print('ERROR:' + error)
      observation.add_error(JsonError(error, e))
      return []

    if not isinstance(doc, list):
      doc = [doc]
    self.filter_all_objects_to_observation(context, doc, observation)

    return observation.objects


class OsClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing OpenStack state."""

  def __init__(self, title, os, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      os: The OsAgent to make the observation for the clause to verify.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
      strict: DEPRECATED flag indicating whether the clauses (added later)
         must be true for all objects (strict) or at least one (not strict).
         See ValueObservationVerifierBuilder for more information.
         This is deprecated because in the future this should be on a per
         constraint basis.
    """
    super(OsClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__os = os
    self.__strict = strict

  def collect_resources(self, command,
                        args=None, filter=None,
                        no_resources_ok=False):
    """Collect the OpenStack resources of a particular type.

    Args:
      command: The openstack command name to run (e.g. 'image', 'server')
      args: An array of strings containing the remaining openstack command
      parameters.
      filter: If provided, a filter to use for refining the collection.
      no_resources_ok: Whether or not the resource is required.
          If the resource is not required, 'resource not found' error is
          considered successful.
    """
    args = args or []
    cmd = self.__os.build_os_command_args(
        command, args, os_cloud=self.__os.os_cloud)

    self.observer = OsObjectObserver(self.__os, cmd)

    if no_resources_ok:
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='"Not Found" permitted.',
          error_regex='(?:.* operation: Cannot find .*)|(?:.*\(.*NotFound\)|(Error .*).*)')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Collect {0} or Not Found'.format(command))
      disjunction_builder.append_verifier(error_verifier)

      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command), strict=self.__strict)
      disjunction_builder.append_verifier_builder(
          collect_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command), strict=self.__strict)
      self.verifier_builder.append_verifier_builder(collect_builder)

    return collect_builder

  def show_resource(self, command, resource_name, no_resources_ok=False):
    """Show the OpenStack resource of a particular type.

    Args:
      command: The openstack command name to run
      (e.g. 'security group', 'server').
      resource_name: Name of the OpenStack resource
      (e.g. Name of a security group or an image).
      no_resources_ok: Whether or not the resource is required.
      If the resource is not required, 'resource not found' error is
      considered successful.
    """
    args = ['show', resource_name, '--format', 'json']

    cmd = self.__os.build_os_command_args(
      command, args, os_cloud=self.__os.os_cloud)
    self.observer = OsObjectObserver(self.__os, cmd)
    if no_resources_ok:
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='"Not Found" permitted.',
          error_regex='(?:.* operation: Cannot find .*)|(?:.*\(.*NotFound\)|(Error .*).*)')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Collect {0} or Not Found'.format(command))
      disjunction_builder.append_verifier(error_verifier)

      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command), strict=self.__strict)
      disjunction_builder.append_verifier_builder(
          collect_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command), strict=self.__strict)
      self.verifier_builder.append_verifier_builder(collect_builder)

    return collect_builder


class OsContractBuilder(jc.ContractBuilder):
  """Specialized contract builder that facilitates observing OpenStack."""

  def __init__(self, os):
    """Constructor.

    Args:
      os: The OsAgent to use for communicating with OpenStack.
    """
    super(OsContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        OsClauseBuilder(
            title, os=os,
            retryable_for_secs=retryable_for_secs, strict=strict))

