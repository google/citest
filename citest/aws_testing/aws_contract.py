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


import json

from .. import json_contract as jc
from ..service_testing import cli_agent

class AwsObjectObserver(jc.ObjectObserver):

  def __init__(self, agent, args, filter=None):
    """Construct new observer.

    Args:
      agent: AwsAgent to observe with.
      args: Command line arguments to pass to aws program.
      filter: If provided, then use this to filter observations.
    """
    super(AwsObjectObserver, self).__init__(filter)
    self._aws = agent
    self._args = args

  def __str__(self):
    return 'AwsObjectObserver({0})'.format(self._args)

  def collect_observation(self, observation, trace=True):
    aws_response = self._aws.run(self._args, trace)
    if aws_response.retcode != 0:
      observation.add_error(cli_agent.CliAgentRunError(self._aws, aws_response))
      return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(aws_response.output)
    except (ValueError, UnicodeError) as e:
      error = 'Invalid JSON in response: %s' % str(aws_response)
      print 'ERROR:' + error
      observation.add_error(jc.JsonError(error, e))
      return []

    if not isinstance(doc, list):
      doc = [doc]
    self.filter_all_objects_to_observation(doc, observation)

    return observation._objects


class AwsClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing AWS state."""

  def __init__(self, title, aws, retryable_for_secs=0):
    super(AwsClauseBuilder, self).__init__(
      title=title, retryable_for_secs=retryable_for_secs)
    self._aws = aws

  def collect_resources(self, aws_module, command, args=[], filter=None,
                        no_resources_ok=False):
    """Collect the AWS resources of a particular type.

    Args:
      aws_module: The aws program module name we're looking in (e.g. 'ec2')
      command: The aws command name to run (e.g. 'describe-instances')
      args: An array of strings containing the remaining aws command parameters.
      filter: If provided, a filter to use for refining the collection.
      no_resources_ok: Whether or not the resource is required.
          If the resource is not required, 'resource not found' error is
          considered successful.
    """
    cmd = self._aws.build_aws_command_args(
        command, args, aws_module=aws_module, profile=self._aws.profile)

    self.observer = AwsObjectObserver(self._aws, cmd)

    if no_resources_ok:
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='"Not Found" permitted.',
          error_regex='.* operation: Cannot find .*')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Collect {0} or Not Found'.format(command))
      disjunction_builder.append_verifier(error_verifier)

      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command))
      disjunction_builder.append_verifier_builder(
          collect_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command))
      self.verifier_builder.append_verifier_builder(collect_builder)

    return collect_builder


class AwsContractBuilder(jc.ContractBuilder):
  """Specialized contract builder that facilitates observing AWS."""

  def __init__(self, aws):
    """Constructor.

    Args:
      aws: The AwsAgent to use for communicating with AWS.
    """
    super(AwsContractBuilder, self).__init__(
        lambda title, retryable_for_secs:
            AwsClauseBuilder(
                title, aws=aws, retryable_for_secs=retryable_for_secs))
