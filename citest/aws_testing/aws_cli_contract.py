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


"""Support for specifying citest.json_contract.Contract on AWS resources."""

import json

from .. import json_contract as jc
from ..json_predicate import JsonError
from ..service_testing import cli_agent

class AwsObjectObserver(jc.ObjectObserver):
  """Observe AWS resources."""

  def __init__(self, agent, args, filter=None):
    """Construct new observer.

    Args:
      agent: AwsCliAgent to observe with.
      args: Command line arguments to pass to aws program.
      filter: If provided, then use this to filter observations.
    """
    super(AwsObjectObserver, self).__init__(filter)
    self.__aws = agent
    self.__args = args

  def __str__(self):
    return 'AwsObjectObserver({0})'.format(self.__args)

  def collect_observation(self, context, observation, trace=True):
    args = context.eval(self.__args)
    aws_response = self.__aws.run(args, trace)
    if not aws_response.ok():
      observation.add_error(
          cli_agent.CliAgentRunError(self.__aws, aws_response))
      return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(aws_response.output)
    except (ValueError, UnicodeError) as e:
      error = 'Invalid JSON in response: %s' % str(aws_response)
      print 'ERROR:' + error
      observation.add_error(JsonError(error, e))
      return []

    if not isinstance(doc, list):
      doc = [doc]
    self.filter_all_objects_to_observation(context, doc, observation)

    return observation.objects


class AwsClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing AWS state."""

  def __init__(self, title, aws, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      gcloud: The AwsCliAgent to make the observation for the clause to verify.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
      strict: DEPRECATED flag indicating whether the clauses (added later)
         must be true for all objects (strict) or at least one (not strict).
         See ValueObservationVerifierBuilder for more information.
         This is deprecated because in the future this should be on a per
         constraint basis.
    """
    super(AwsClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__aws = aws
    self.__strict = strict

  def collect_resources(self, aws_module, command,
                        args=None, filter=None,
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
    args = args or []
    cmd = self.__aws.build_aws_command_args(
        command, args, aws_module=aws_module, profile=self.__aws.profile)

    self.observer = AwsObjectObserver(self.__aws, cmd)

    if no_resources_ok:
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='"Not Found" permitted.',
          error_regex='(?:.* operation: Cannot find .*)|(?:.*\(.*NotFound\).*)')
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


class AwsCliContractBuilder(jc.ContractBuilder):
  """Specialized contract builder that facilitates observing AWS."""

  def __init__(self, aws):
    """Constructor.

    Args:
      aws: The AwsCliAgent to use for communicating with AWS.
    """
    super(AwsCliContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        AwsClauseBuilder(
            title, aws=aws,
            retryable_for_secs=retryable_for_secs, strict=strict))
