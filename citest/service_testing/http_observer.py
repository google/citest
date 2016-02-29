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
import traceback

# citest modules.
import citest.json_contract as jc
from . import AgentError


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
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_mechanism(entity, 'Agent', self.__agent)
    snapshot.edge_builder.make_control(entity, 'Path', self.__path)
    super(HttpObjectObserver, self).export_to_json_snapshot(snapshot, entity)

  def collect_observation(self, observation, trace=True):
    # This is where we'd use an HttpAgent to get a URL then
    # collect some thing out of the results.
    result = self.agent.get(self.__path, trace=trace)
    if not result.ok():
      error = 'Observation failed with HTTP %s.\n%s' % (result.http_code,
                                                        result.error)
      logging.getLogger(__name__).error(error)
      observation.add_error(AgentError(error))
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
      observation.add_error(jc.JsonError(error, ex))
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

  def get_url_path(self, path):
    """Perform the observation using HTTP GET on a path.

    Args:
      path [string]: The path relative to the agent's baseUrl.
    """
    self.observer = HttpObjectObserver(self.__agent, path)
    observation_builder = jc.ValueObservationVerifierBuilder(
        'Get ' + path, strict=self.__strict)
    self.verifier_builder.append_verifier_builder(observation_builder)
    return observation_builder
