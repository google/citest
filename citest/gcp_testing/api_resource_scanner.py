# Copyright 2018 Google Inc. All Rights Reserved.
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

"""Support for filtering resources and instances with the ApiNavigator."""


import collections
import re
import urllib2
import urlparse
from googleapiclient.errors import HttpError

from citest.base import ExecutionContext
from citest.gcp_testing.gcp_agent import GcpAgent

__AGENT_CACHE = {}


def _gcp_agent_singleton(**kwargs):
  """Manage singleton of agents to particular apis.

    This treates the agent instances as singletons based on their configuration.
    The reason for this is simply to reduce logging noise on the creation.
    This is possible since agents are stateless.

  Args:
    kargs: [kwargs]  Arguments to GcpAgent.make_agent
  """
  # pylint: disable=global-statement
  global __AGENT_CACHE
  key = str(kwargs)
  if key not in __AGENT_CACHE:
    __AGENT_CACHE[key] = GcpAgent.make_agent(**kwargs)

  return __AGENT_CACHE[key]


def get_metadata(relative_url):
  """Return metadata value.

  Args:
    relative_url: [string] Metadata url to fetch relative to base metadata URL.
  """
  base_url = 'http://metadata/computeMetadata/v1/'
  url = urlparse.urljoin(base_url, relative_url)
  headers = {'Metadata-Flavor': 'Google'}
  return urllib2.urlopen(urllib2.Request(url, headers=headers)).read()


_ApiResourceScannerListHelperResult = collections.namedtuple(
    '_ApiResourceScannerListHelperResult',
    ['params', 'method_name', 'resources'])


class ResourceList(
    collections.namedtuple('ResourceList',
                           ['aggregated', 'params', 'response'])):
  """A collection of resource instances and their container parameters.


  Attributes:
    aggregated: [bool] If true, the result is from an aggregatedList.
        Aggregated list results are in the form (key, value) where
        key is the key from the aggregatedListResponse and value is the
        value for that key. Otherwise the response is just the list of values.
    params: [dict] The parameters used to query the list
    response: [list] The list of values from the query. These are not the full
        response json dictionaries, rather just the entity name/identifier.
  """

  def stringify(self, resource):
    """Convert to string.

    Args:
      resource: [string] The name of the resource this result was from.
    """
    bindings = ', '.join(['{0}={1}'.format(name, value)
                          for name, value in self.params.items()])
    lines = ['RESOURCE {0}({1}) + {2}'.format(
        resource, bindings, len(self.response))]
    for name in self.response:
      lines.append('  * {0}'.format(name))
    return '\n'.join(lines)


class ComputeApiResourceHelper(object):
  """Helper functions for interacting with the compute API."""

  @property
  def all_zones(self):
    """Return all the known compute zones."""
    if not self.__all_zones:
      self.__all_zones = [
          item['name']
          for item in self.__agent.list_resource(ExecutionContext(), 'zones')]
    return self.__all_zones

  @property
  def all_regions(self):
    """Return all the available GCE regions."""
    if not self.__all_regions:
      self.__all_regions = [
          item['name']
          for item in self.__agent.list_resource(ExecutionContext(), 'regions')]
    return self.__all_regions

  def __init__(self, compute_agent):
    self.__agent = compute_agent
    self.__all_zones = None
    self.__all_regions = None


class ApiResourceScanner(object):
  """Support for scanning API resources and their instances.

  Terminology:
     Resource: A category/type of thing that the API is managing.
     Instance: Instances of resources managed by the API.
  """

  # Synthetic method name hinting we need to list for each 'zone'
  LIST_BY_ZONE = 'listByZone'
  # Synthetic method name hinting we need to list for each 'region'
  LIST_BY_REGION = 'listByRegion'

  @property
  def credentials_path(self):
    """Credentials used when scanning apis."""
    return self.__credentials_path

  @property
  def default_variables(self):
    """Default variable bindings when calling API methods using them."""
    return self.__default_variables

  @property
  def investigator(self):
    """Bound ApiInvestigator."""
    return self.__investigator

  def __init__(self, investigator, credentials_path, default_variables=None):
    """Constructor

    Args:
      investigator: [ApiInvestigator] used to analyze APIs
      credentials_path: [string] Path to credentials to use when scanning APIs.
      default_variables: [dict] API variable bindings to use when relevant.
    """
    bindings = dict(default_variables) if default_variables else {}
    in_project = bindings.get('project')
    for which in ['project', 'projectId']:
      if not bindings.get(which):
        if not in_project:
          try:
            in_project = get_metadata('project/project-id')
          except IOError:
            continue
        bindings[which] = in_project

    self.__investigator = investigator
    self.__credentials_path = credentials_path
    self.__default_variables = bindings

    agent = self.make_agent(
        'compute', 'https://www.googleapis.com/auth/compute.readonly')
    self.__compute_api_resource_helper = ComputeApiResourceHelper(agent)

  def make_agent(self, api, default_scope, default_variables=None):
    """Construct an agent to talk to a Google API.

    Args:
      api: [string] The API name containing the resources.
      default_scope: [string] The OAuth scope to use.
         This is only considered if given a credentials_path.
    """
    version = self.__investigator.get_api_version(api)
    credentials = self.__credentials_path or None
    default_variables = default_variables or self.__default_variables

    return _gcp_agent_singleton(
        api=api, version=version,
        scopes=[default_scope],
        credentials_path=credentials,
        default_variables=default_variables)

  def list_api(self, api, item_filter=None):
    """List the instances of an API."""
    result = {}
    errors = {}

    scope_map = self.__investigator.get_api_scope_map(api)
    for scope, scope_resource_names in scope_map.items():
      try:
        agent = self.make_agent(api, scope)
      except HttpError as err:
        print('E Could not create agent'
              'for "{0}" with scope={1}: {2}'
              .format(api, scope, err))
        continue

      for resource in scope_resource_names:
        resource_list, error = self.__collect_resource_list(
            agent, resource, item_filter)
        if resource_list is not None:
          result[resource] = resource_list
        if error is not None:
          errors[resource] = error

    return result, errors

  def __collect_resource_list(self, agent, resource, item_filter):
    """Collect the ResourceList for the given resource."""
    method_name, transform, error_msg = (
        self.__determine_list_method_and_transform(agent, resource))
    if method_name is None:
      return None, error_msg

    try:
      params, method_name, instances = self.__list_resource_helper(
          agent, method_name, resource, transform)
      if item_filter:
        if method_name == 'aggregatedList':
          instances = [item for item in instances if item_filter(item[1])]
        else:
          instances = [item for item in instances if item_filter(item)]
    except (TypeError, ValueError, HttpError) as err:
      import traceback
      traceback.print_exc()
      return None, err.args[0] if err.args else str(err)

    if instances and method_name == 'aggregatedList':
      answers = []
      for values in instances:
        key = values[0]
        entry = values[1]
        answers.append((key, entry.get('name') or entry.get('id')
                        or entry.get('selfLink') or entry))

      resource_list = ResourceList(True, params, answers)
    elif instances and isinstance(instances[0], dict):
      resource_list = ResourceList(
          False, params, [entry.get('name') or entry.get('id')
                          or entry.get('selfLink') or 'UNKNOWN '+str(entry)
                          for entry in instances])
    else:
      resource_list = ResourceList(False, params, instances)

    return resource_list, error_msg

  def __list_resource_helper(self, agent, method_name, resource, transform):
    """Helper function for listing resources.

    This function will associate the parameters used to invoke the function
    with the results from the function so that the listed results can be
    operated on again in the future (e.g. delete) where additional parameters
    for their context might be needed (e.g. project, zone, etc).

    Normally this will either call list or listAggregated
    (for some Compute APIs). The listAggregated response is actually a
    composite response containing a dictionary keyed by the parameter
    aggregated over (e.g. zone) and whose value is the result list for that
    particular zone. This method unpacks that dictionary into a list of
    tuples where the first element is the key (e.g. identifying the zone)
    and the second element is the result value (the inner item data list.
    For normal 'list' methods, this returns just the non-tupled item list.
    The tuple form communicates an additional [implied] parameter that will
    be needed to retrieve or operate on the item.

    This module introduces some fake "method_name" parameters for synthetic
    aggregation. If the method is LIST_BY_ZONE then this function will manually
    iterate over each ZONE and perform a 'list' operation, but return the
    results from all these queries as if it were a single 'listAggregated'
    call. This is to support APIs that do not have a listAggregated method
    but require a zone or region parameter.

    The method that calls this figures out whether or not it should iterate
    over zones or regions when passing i the "method name". If one of these
    synthetic methods is passed in, the result will report as if it came
    from 'aggregatedList' even though this method does not actually exist.
    This is so other functions dont need additional special cases since the
    result schema is the same as if there were an "aggregatedList".
    """

    context = ExecutionContext()

    if method_name == self.LIST_BY_ZONE:
      param_name = 'zone'
      param_variants = self.__compute_api_resource_helper.all_zones
    elif method_name == self.LIST_BY_REGION:
      param_name = 'region'
      param_variants = self.__compute_api_resource_helper.all_regions
    else:
      params = agent.resource_method_to_variables(method_name, resource)
      return _ApiResourceScannerListHelperResult(
          params, method_name, agent.list_resource(
              context, resource,
              method_variant=method_name,
              item_list_transform=transform))

    params = agent.resource_method_to_variables(
        'list', resource, **{param_name: 'tbd'})
    items = []
    for param_value in param_variants:
      results = agent.list_resource(
          context, resource, method_variant='list',
          **{param_name: param_value})
      items.extend([('{0}s/{1}'.format(param_name, param_value), item)
                    for item in results])
    return _ApiResourceScannerListHelperResult(params, 'aggregatedList', items)

  def __determine_list_method_and_transform(self, agent, resource):
    """Determine which list method to use, and result transform for it.

    We'll use either list or aggregatedList or None depending on what
    is available, the parameters it requires, and the arguments we have.

    Args:
       agent: [GcpAgent] The agent for talking to the service
    """
    error = None
    for method_name in ['list', 'aggregatedList']:
      try:
        agent.resource_method_to_variables(method_name, resource,
                                           **agent.default_variables)
        if method_name == 'list':
          return 'list', None, None

        path = (agent.discovery_document['resources'][resource]
                ['methods'][method_name]['path'])
        data_label = path.split('/')[-1]
        def transform(items):
          # pylint: disable=missing-docstring
          result = []
          for key, entry_values in items.items():
            data_values = entry_values.get(data_label, None)
            if data_values:
              result.extend([(key, value) for value in data_values])
          return result
        return 'aggregatedList', transform, None
      except KeyError:
        pass  # Unknown method
      except ValueError as err:
        error = err.args[0] if err.args else str(err)
        # Maybe try again if more remaining.

    if re.search(r"missing required parameters.*\[u?'zone'\]", error):
      return self.LIST_BY_ZONE, None, None
    elif re.search(r"missing required parameters.*\[u?'region'\]", error):
      return self.LIST_BY_REGION, None, None

    return None, None, error
