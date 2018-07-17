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

"""Collects resources managed by Google APIs."""

import collections
import re

from citest.gcp_testing.gcp_agent import GcpAgent
from citest.base import ExecutionContext

ApiInvestigatorMethodability = collections.namedtuple(
    'ApiInvestigatorMethodability',
    ['listable', 'unlistable', 'scope_map'])

class ApiResourceFilter(object):
  """Determines which resources in an API are wanted."""
  # pylint: disable=too-few-public-methods

  def __init__(self, include_regex_list, exclude_regex_list):
    """Constructor.

    Args:
      include_regex_list: [list of re] Regexes to include.
      exclude_regex_list: [list of re] Regexes to subtract from include.
    """
    self.__include = include_regex_list
    self.__exclude = exclude_regex_list

  def __repr__(self):
    return 'ApiResourceFilter\n  %r\n  %r' % (self.__include, self.__exclude)

  def wanted(self, resource_name):
    """Determine if resource_name is among those included but not excluded."""
    found = False
    for exp in self.__include:
      if exp.match(resource_name):
        found = True
        break

    if found:
      for exp in self.__exclude:
        if exp.match(resource_name):
          found = False
          break

    return found


class ApiInvestigator(object):
  """Investigate APIs for what resources they manage and how to inspect them."""

  __api_version_map = None

  @staticmethod
  def collect_apis():
    """Collect names and current versions of all the Google APIs."""
    if ApiInvestigator.__api_version_map:
      return ApiInvestigator.__api_version_map

    context = ExecutionContext()
    agent = GcpAgent.make_agent(api='discovery', version='v1')
    apis = agent.list_resource(context, 'apis')

    catalog = {}
    for entry in apis:
      preferred = entry.get('preferred', True)
      if not preferred:
        continue
      catalog[entry['name']] = entry['version']

    ApiInvestigator.__api_version_map = catalog
    return catalog

  @staticmethod
  def get_api_version(api):
    """Return current version of requested api name."""
    return ApiInvestigator.collect_apis()[api]

  def pick_scope(self, choices, api, mutable=False):
    """Given a list of scopes, pick the "safest" one.

    By "safest" we mean one that is the closest match for read (not mutable)
    or write (mutable). We're just guessing blind here. We'll prefer a
    read/write-only scope on the resource itself and work our way back from
    there if we cannot find it one.

    Args:
      choices: [list of string]  List of auth scopes to pick from.
      api: [string]  The name of the resource API the scope is for.
      mutable: [boolean]  False for a read-only scope. True for write-only.
    """
    if not choices:
      return None

    best_name = 'write' if mutable else 'read'
    best = [choice for choice in choices if choice.find(best_name) >= 0]
    if len(best) == 1:
      return best[0]

    only = [choice for choice in best if choice.find('only') > 0]
    if len(only) == 1:
      return only[0]

    # Either nothing was best_name or there are multiple ones.
    # Either way, lets rule out an unpreferred scopes. This will cause us
    # to favor "read" or "read_only" over "read_write" for mutable
    # and to favor "full" scopes if mutable and no "write" scope listed.
    alternative = [choice for choice in (only or best or choices)
                   if (mutable and choice.find('full') > 0
                       or not mutable and choice.find('write') < 0)]
    if len(alternative) == 1:
      return alternative[0]

    # Since we did not find a scope limited to read
    # attempt to locate one that is defined by our API itself
    # as opposed to giving more global permissions.
    special = [choice for choice in (only or best or alternative or choices)
               if choice.find(api) > 0]

    if special:
      return special[0]

    # Just pick one.
    return (only or best or alternative or choices)[0]

  def __init__(self, api_to_resource_filter_map):
    """
    Args:
        api_to_resource_filter_map: [map of <api name, ApiResourceFilter>]
    """
    self.__api_to_resource_filter_map = api_to_resource_filter_map
    self.__methodability_cache = {}

  def get_listable_api_resources(self, api):
    """Returns list of API resources that the Investigator can list.

    Listable API resources have a "list" or "aggregatedList" method.
    """
    return self.get_methodability(api).listable

  def get_unlistable_api_resources(self, api):
    """Returns list of API resources that the Investigator cannot list.

    Unlistable API resources do not have a listable method.
    """
    return self.get_methodability(api).unlistable

  def get_api_scope_map(self, api):
    """Returns the API scope map needed when interacting with methods."""
    return self.get_methodability(api).scope_map

  def get_api_resource_filter(self, api):
    """Returns ApiResourceFilter for named api, or None if not known."""
    return self.__api_to_resource_filter_map.get(api)

  def get_methodability(self, api):
    """Determine the ApiInvestigatorMethodability for the api.

    Typically the individual accessor methods are used instead of this.
    Returns:
       ApiInvestigatorMethodability for the given API
    """
    if api not in self.__methodability_cache:
      version = self.get_api_version(api)
      listable, unlistable = self.find_listable_resources(
          api, version, self.__api_to_resource_filter_map[api])
      scope_map = self.determine_scope_map(listable, api)
      self.__methodability_cache[api] = ApiInvestigatorMethodability(
          listable, unlistable, scope_map)
    return self.__methodability_cache[api]

  def determine_scope_map(self, resources, api, mutable=False):
    """Determine the scope we'll need to list each API.

    Args:
      resources: [map of resource, method_spec] The resources to map
      api: [string] The name of the api containing the resource.

    Returns:
       This returns an inverse map keyed by the scope and containing
       all the APIs that use that scope. This is more useful because we'll
       be reusing the scoped client where we can.
    """
    resource_to_scope = {
        key : self.pick_scope(value.get('scopes'), api, mutable=mutable)
        for key, value in resources.items()}
    scope_to_resource = {}
    for resource, scope in resource_to_scope.items():
      if scope in scope_to_resource:
        scope_to_resource[scope].add(resource)
      else:
        scope_to_resource[scope] = set([resource])
    return scope_to_resource

  def find_listable_resources(self, api, version, resource_filter):
    """Find all the resources within an API that we can list elements of.

    Args:
      api: [string] The API name containing the resources.
      version: [string] The API version.
      resource_filter: [ApiResourceFilter] Determines resource names to match.

    Returns:
      Map of resource name to the method specification for listing it.
    """
    doc = GcpAgent.download_discovery_document(api, version)
    resources = doc['resources']
    return self.__find_listable_resources_helper(
        None, resources, resource_filter)

  def __find_listable_resources_helper(
      self, container, resources, resource_filter):
    """Helper method for find_listable_resources.

    This is potentially recursive to handle nested resources.
    We ignore resources that are not listable as well as resources that
    are listable but not deletable since there's nothing we can do about them.
    These are likely constant resources (e.g. regions).

    Args:
      container: [string] The parent resource, if any.
      resources: [list of resource specification] The discovery document
          resource specification to look for a list method within.
      resource_filter: [ResourceFilter] Determines resource names to match.
    """
    listable = {}
    unlistable = set()
    undeletable = set()
    container_prefix = '{0}.'.format(container) if container else ''
    for name, value in resources.items():
      key = '{prefix}{name}'.format(prefix=container_prefix, name=name)
      children = value.get('resources')
      if children:
        sub_listable, sub_unlistable = self.__find_listable_resources_helper(
            key, children, resource_filter)
        listable.update(sub_listable)
        unlistable = unlistable.union(sub_unlistable)
      if not resource_filter.wanted(key):
        continue

      methods = value.get('methods') or {}
      list_method = methods.get('aggregatedList') or methods.get('list')
      if list_method:
        if methods.get('delete'):
          listable[key] = list_method
        else:
          undeletable.add(key)  # Ignored for now.
      else:
        unlistable.add(key)
    return listable, unlistable

  def determine_required_parameters(self, method_spec):
    """Determine which parameters are required within a method specification.

    Args:
      method_spec: [string] The specification from the discovery document.

    Returns:
      map of parameter name to the parameter specification.
    """
    result = {}
    parameters = method_spec.get('parameters', {})
    for key, key_spec in parameters.items():
      if key_spec.get('required', False):
        result[key] = key_spec
    return result

  def stringify_api(self, api):
    """Print API to stdout."""
    methodability = self.get_methodability(api)
    lines = ['API:  "{api}"'.format(api=api)]
    if methodability.unlistable:
      lines.append('  UNLISTABLE')
      for name in methodability.unlistable:
        lines.append('    * {0}'.format(name))

    for scope, resource_list in methodability.scope_map.items():
      lines.append('  {0}'.format(scope))
      for name in resource_list:
        lines.append('    * {0}: params=({1})'.format(
            name,
            ', '.join([key
                       for key in self.determine_required_parameters(
                           methodability.listable[name])])))
    lines.append('-' * 40 + '\n')
    return '\n'.join(lines)

  def foreach_api(self, func):
    """Execute a function for each api name of interest."""
    return {api: func(api) for api in self.__api_to_resource_filter_map.keys()}


class ApiInvestigatorBuilder(object):
  """Class builds a ApiInvestigator with api filtering."""

  @property
  def include_apis(self):
    """Map of api/resource names to regex of instance names to find."""
    return self.__include_apis

  @include_apis.setter
  def include_apis(self, apis):
    """Map of api/resource names to regex of instance names to find."""
    if not isinstance(apis, list):
      raise TypeError('Expected list')
    self.__include_apis = apis

  @property
  def exclude_apis(self):
    """Map of api/resource names to regex of instance names to igore."""
    return self.__exclude_apis

  @exclude_apis.setter
  def exclude_apis(self, apis):
    """Map of api/resource names to regex of instance names to igore."""
    if not isinstance(apis, list):
      raise TypeError('Expected list')
    self.__exclude_apis = apis

  def __init__(self):
    self.__include_apis = None
    self.__exclude_apis = None

  def build(self):
    """Build map of api name to ApiResourceFilter."""
    version_map = ApiInvestigator.collect_apis()
    exclude = self.__exclude_apis or []
    include = (self.__include_apis
               if self.__include_apis is not None else ['all'])
    if include == ['all']:
      include = version_map.keys()

    api_to_include_map = self.__make_apis_to_regex_map(include)
    api_to_exclude_map = self.__make_apis_to_regex_map(exclude)

    bad_apis = [api for api in api_to_include_map
                if not api in version_map]
    bad_apis.extend([api for api in api_to_exclude_map
                     if not api in version_map])
    if bad_apis:
      raise KeyError(
          'Unknown apis: {0}'.format(', '.join(['"{0}"'.format(s)
                                                for s in bad_apis])))

    api_to_resource_filter_map = {
        api: ApiResourceFilter(api_to_include_map[api],
                               api_to_exclude_map.get(api) or [])
        for api in api_to_include_map
    }

    return ApiInvestigator(api_to_resource_filter_map)


  @staticmethod
  def __make_apis_to_regex_map(api_list):
    """Return a dictionary of apis and distinct resource filters for each."""
    roots = {}
    for elem in api_list:
      parts = elem.split('.', 1)
      root = parts[0]
      value = r'\*' if len(parts) == 1 else re.escape(parts[1])
      value = value.replace(r'\*', '.*')
      if root in roots:
        roots[root].add(re.compile('^' + value))
      else:
        roots[root] = set([re.compile('^' + value)])
    return roots
