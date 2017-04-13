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


"""Support for specifying citest.json_contract.Contract on AWS resources."""

import json
import logging
import re
import traceback

from botocore.exceptions import (BotoCoreError, ClientError)

from .. import json_contract as jc


class AwsErrorVerifier(jc.ObservationFailureVerifier):
  def __init__(self, title, regex='.*'):
    super(AwsErrorVerifier, self).__init__(title)
    self.__re = re.compile(regex)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    super(AwsErrorVerifier, self).export_to_json_snapshot(
        snapshot, entity)
    snapshot.edge_builder.make_control(entity, 'regex', self.__re.pattern)

  def _error_comment_or_none(self, error):
    if isinstance(error, (BotoCoreError, ClientError)):
      if self.__re.search(error.message):
        return 'Found "{0}"'.format(error)
    return None


class AwsObjectObserver(jc.ObjectObserver):
  """Observe AWS resources."""

  def __init__(self, method, *pos_args, **kwargs):
    """Construct new observer.

    Args:
      method: [callable] Method to invoke.
      pos_args: [list] Positional arguments for method.
      kwargs: [kwargs] Additional arguments to pass to method.
    """
    super(AwsObjectObserver, self).__init__()
    self.__method = method
    self.__pos_args = pos_args
    self.__kwargs = dict(kwargs)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    if self.__pos_args:
      snapshot.edge_builder.make_control(
          entity, '#PosArgs', len(self.__pos_args))
    if self.__kwargs:
      snapshot.edge_builder.make_control(
          entity, 'KwargKeys', self.__kwargs.keys())
    super(AwsObjectObserver, self).export_to_json_snapshot(snapshot, entity)

  def __str__(self):
    return 'AwsObjectObserver({0})'.format(self.__kwargs)

  def collect_observation(self, context, observation, trace=True):
    try:
      doc = self.__method(context, *self.__pos_args, **self.__kwargs)
    except (BotoCoreError, ClientError) as error:
      # This isnt necessarily an error because we might have been expecting it.
      logging.getLogger(__name__).info('%s\n%s\n----------------\n',
                                       error, traceback.format_exc())
      observation.add_error(error)
      return []

    if not isinstance(doc, list):
      doc = [doc]
    self.filter_all_objects_to_observation(context, doc, observation)
    return observation.objects


class AwsPythonClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitates observing AWS state."""

  def __init__(self, title, aws_agent, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Args:
      title: The string title for the clause is only for reporting purposes.
      aws_agent: The AwsPythonAgent to make the observation for the clause.
      retryable_for_secs: Number of seconds that observations can be retried
         if their verification initially fails.
      strict: DEPRECATED flag indicating whether the clauses (added later)
         must be true for all objects (strict) or at least one (not strict).
         See ValueObservationVerifierBuilder for more information.
         This is deprecated because in the future this should be on a per
         constraint basis.
    """
    super(AwsPythonClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__aws_agent = aws_agent
    self.__strict = strict

  def call_method(self, method, *pos_args, **kwargs):
    """Call a method with the provided arguments.

    Args:
      method: The method to call is probably on the instance returned by
          agent.make_client().
      pos_args: [list] Positional arguments for method.
      kwargs: [kwargs] Depends on the resource being collected.
    """
    self.observer = AwsObjectObserver(
        self.__aws_agent.call_method, method, *pos_args, **kwargs)

    observation_builder = jc.ValueObservationVerifierBuilder(
        'Call ' + method.__name__, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)
    return observation_builder

  def call_method_and_extract_singular_response(
       self, method, *pos_args, **kwargs):
    """Call the method and return the one result it resturns.

      method: The method to call is probably on the instance returned by
          agent.make_client().
      pos_args: [list] Positional arguments for method.
       kwargs: [kwargs] Depends on the resource being collected.
   """
    self.observer = AwsObjectObserver(
        self.__aws_agent.call_method_and_extract_singular_response,
        method, *pos_args, **kwargs)

    observation_builder = jc.ValueObservationVerifierBuilder(
        'Get result from ' + method.__name__, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)
    return observation_builder


class AwsPythonContractBuilder(jc.ContractBuilder):
  """Specialized contract builder that facilitates observing AWS."""

  def __init__(self, aws_agent, clause_factory=None):
    """Constructor.

    Args:
      aws_agent: The AwsPythonAgent to use for communicating with AWS.
      clause_factory: [factory creating a ContractClauseBuilder]
    """
    if clause_factory is None:
      clause_factory = (
          lambda title, retryable_for_secs=0, strict=False:
          AwsPythonClauseBuilder(
              title, aws_agent=aws_agent,
              retryable_for_secs=retryable_for_secs, strict=strict))
    super(AwsPythonContractBuilder, self).__init__(clause_factory)
