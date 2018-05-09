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

"""Implements an Observer on an HTTP server."""


# Standard python modules.
import json
import logging
import re
import traceback

# citest modules.
import citest.json_contract as jc
from citest.json_predicate import JsonError
from . import AgentError


class HttpAgentError(AgentError):
  """A specialization of AgentError that contain an HTTP error response."""

  @property
  def http_result(self):
    """The HttpResponseType instance"""
    return self.__http_result

  def __init__(self, http_result):
    """Constructor.

    Args:
      http_result: [HttpResponseType] The HTTP error response.
    """
    error = 'Observation failed with HTTP %s.\n%s' % (http_result.http_code,
                                                      http_result.output)
    super(HttpAgentError, self).__init__(error)
    self.__http_result = http_result



class HttpObjectObserver(jc.ObjectObserver):
  """Observe objects within an HTTP server using direct HTTP invocations."""
  @property
  def agent(self):
    """The HttpAgent used to make observations is bound in the constructor."""
    return self.__agent

  def __init__(self, agent, path, filter=None):
    """Construct observer.

    Args:
      agent: [HttpAgent] Instance to use.
      path: [string] Path to GET from server that agent is bound to.
    """
    # pylint: disable=redefined-builtin
    super(HttpObjectObserver, self).__init__(filter)
    self.__agent = agent
    self.__path = path

  def __str__(self):
    return 'HttpObjectObserver({0})'.format(self.__agent)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Agent', self.__agent)
    snapshot.edge_builder.make_control(entity, 'Path', self.__path)
    super(HttpObjectObserver, self).export_to_json_snapshot(snapshot, entity)

  def collect_observation(self, context, observation):
    # This is where we'd use an HttpAgent to get a URL then
    # collect some thing out of the results.
    result = self.agent.get(context.eval(self.__path))
    if not result.ok():
      http_agent_error = HttpAgentError(result)
      logging.getLogger(__name__).info(http_agent_error)
      observation.add_error(http_agent_error)
      return []

    return self._do_decode_objects(result.output, observation)

  def _do_decode_objects(self, content, observation):
    """Implements helper method to extract observed objects.

    Args:
      content [string]: A JSON encoded string containing the observation.
      observation [Observation]: The observation we are building.

    Returns:
      The current list of objects we've observed so far.
    """
    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(content)
      if not isinstance(doc, list):
        doc = [doc]
      observation.add_all_objects(doc)
    except ValueError as ex:
      error = 'Invalid JSON in response: %s' % content
      logging.getLogger(__name__).info('%s\n%s\n----------------\n',
                                       error, traceback.format_exc())
      observation.add_error(JsonError(error, ex))
      return []

    return observation.objects


class HttpContractBuilder(jc.ContractBuilder):
  """ContractBuilder for contracts based on observing an HTTP server."""

  def __init__(self, agent):
    """Constructor.

    Args:
      agent [HttpAgent]: The HTTP agent that the clauses will observe with.
    """
    super(HttpContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        HttpContractClauseBuilder(
            title=title, agent=agent,
            retryable_for_secs=retryable_for_secs, strict=strict))


class HttpContractClauseBuilder(jc.ContractClauseBuilder):
  """Build clauses based on HTTP endpoint queries."""

  def __init__(self, title, agent, retryable_for_secs=0, strict=False):
    """Construct builder.

    Args:
      title [string]: The title of the clause for reporting.
      agent [HttpAgent]: The HTTP agent the clause is observing with.
      retryable_for_secs [int]: Seconds to retry the observation if needed.
      strict [bool]: Whether verification is strict or not.
    """
    super(HttpContractClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__agent = agent
    self.__strict = strict

  def get_url_path(self, path, allow_http_error_status=None):
    """Perform the observation using HTTP GET on a path.

    Args:
      path [string]: The path relative to the agent's baseUrl.
      allow_http_error_status: [int] If not None then we allow this HTTP error
         status as a valid response without further constraints. For example
         404 would mean that we permit a 404 error, otherwise we may expect
         other constraints on the observed path as a normal clause would
         specify.
    """
    self.observer = HttpObjectObserver(self.__agent, path)
    if allow_http_error_status:
      error_verifier = HttpObservationFailureVerifier(
          'Got HTTP {0} Error'.format(allow_http_error_status),
          allow_http_error_status)
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Get url {0} or {1}'.format(path, allow_http_error_status))
      disjunction_builder.append_verifier(error_verifier)

      observation_builder = jc.ValueObservationVerifierBuilder(
          'Get url {0}'.format(path))
      disjunction_builder.append_verifier_builder(
          observation_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      observation_builder = jc.ValueObservationVerifierBuilder(
          'Get ' + path, strict=self.__strict)
      self.verifier_builder.append_verifier_builder(observation_builder)

    return observation_builder


class HttpObservationFailureVerifier(jc.ObservationFailureVerifier):
  """An ObservationVerifier that expects specific errors from HTTP."""

  def __init__(self, title, http_code, error_regex=None):
    """Constructs the clause with the acceptable error code.

    Args:
      title: [string] Verifier name for reporting purposes only.
      http_code: [int] http code expected.
      error_regex: Regex pattern for errors we're looking for,
                   or None for code only.
    """
    super(HttpObservationFailureVerifier, self).__init__(title)
    self.__http_code = http_code
    self.__error_regex = error_regex

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'HTTP Code', self.__http_code)
    if self.__error_regex:
      snapshot.edge_builder.make_control(entity, 'Regex', self.__error_regex)
    super(HttpObservationFailureVerifier, self).export_to_json_snapshot(
        snapshot, entity)

  def _error_comment_or_none(self, error):
    if not isinstance(error, HttpAgentError):
      raise TypeError('Expected an HttpAgentError. Got "{0}"'.format(error))

    http_result = error.http_result
    if self.__http_code and self.__http_code != http_result.http_code:
      return None

    if (self.__error_regex
        and not re.search(self.__error_regex, http_result.output)):
      return None

    # Return summary of finding the expected error.
    if self.__http_code:
      return 'Observed expected HTTP {0}'.format(self.__http_code)
    if self.__error_regex:
      return 'Observed expected error matching {0}'.format(self.__error_regex)
    return error
