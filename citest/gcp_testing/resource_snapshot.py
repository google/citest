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

# pylint: disable=star-args
# pylint: disable=global-statement

"""Collects resources managed by Google APIs.

Usage:
  # Snapshot everything in compute and storage APIs from the
  # GCP project we are running in and write to a file called 'baseline'.
  # If listing a resource requires a "bucket" parameter, use "my-bucket".
  # (project or projectId parameters will be the local project).
  python citest/gcp_testing/resource_snapshot.py \
      --bindings=bucket=my-bucket \
      --output_file=baseline \
      compute storage

  # Snapshot everything in compute and storage APIs from the
  # GCP project "my-project" and write to a file called 'delta'.
  # Use the credentials in the file "credentials.json" to authenticate APIs.
  # If listing a resource requires a "bucket" parameter, use "my-bucket".
  # (project or projectId parameters will be "my-project").
  python citest/gcp_testing/resource_snapshot.py \
      --project=my-project
      --bindings=bucket=my-bucket \
      --output_file=delta \
      --credentials_path=credentials.json \
      compute storage

  # Print the difference between the 'baseline' and 'delta' snapshots.
  python citest/gcp_testing/resource_snapshot.py \
      --compare baseline delta

  # Delete the API resources in the delta snapshot that are not in the
  # baseline. However since this is a "dry run" it will only show what would
  # have otherwise been deleted.
  python citest/gcp_testing/resource_snapshot.py \
      --compare baseline delta \
      --delete_after \
      --dry_run

  # Collect and print all the images created today.
  python citest/gcp_testing/resource_snapshot.py \
      --list \
      --days_since 0 \
      compute.images

  # Delete all the "candidate" images more than 10 days old.
  python citest/gcp_testing/resource_snapshot.py \
      --delete_list \
      --days_before 10 \
      --name ".*candidate.*" \
      compute.images


  When comparing results, returns non-0 exit code if snapshots differ.
"""

import argparse
import collections
import datetime
import httplib
import json
import pickle
import re
import time
import urllib2
import urlparse

from googleapiclient.errors import HttpError

from citest.gcp_testing.gcp_agent import GcpAgent
from citest.base import ExecutionContext


_RETRYABLE_DELETE_HTTP_CODES = [httplib.CONFLICT, httplib.SERVICE_UNAVAILABLE]


LIST_BY_ZONE = 'listByZone'
LIST_BY_REGION = 'listByRegion'
_compute_agent = None
_all_zones = []
_all_regions = []

ListedResources = collections.namedtuple(
    'ListedResources', ['params', 'method_name', 'resources'])

AttemptedResourceDeletes = collections.namedtuple(
  'AttemptedResourcesDeletes', ['agent', 'aggregated', 'code_to_results'])


def get_all_zones():
  """Get all the available GCE zones."""
  global _all_zones
  if not _all_zones:
    _all_zones = [
        item['name']
        for item in _compute_agent.list_resource(ExecutionContext(), 'zones')]
  return _all_zones

def get_all_regions():
  """Get all the available GCE regions."""
  global _all_regions
  if not _all_regions:
    _all_regions = [
        item['name']
        for item in _compute_agent.list_resource(ExecutionContext(), 'regions')]

  return _all_regions


def get_metadata(relative_url):
  """Return metadata value.

  Args:
    relative_url: [string] Metadata url to fetch relative to base metadata URL.
  """
  base_url = 'http://metadata/computeMetadata/v1/'
  url = urlparse.urljoin(base_url, relative_url)
  headers = {'Metadata-Flavor': 'Google'}
  return urllib2.urlopen(urllib2.Request(url, headers=headers)).read()

def binding_string_to_dict(raw_value):
  """Convert comma-delimted kwargs argument into a normalized dictionary.

  Args:
    raw_value: [string] Comma-delimited key=value bindings.
  """
  kwargs = {}
  if raw_value:
    for binding in raw_value.split(','):
      name, value = binding.split('=')
      if value.lower() == 'true':
        value = True
      elif value.lower() == 'false':
        value = False
      elif value.isdigit():
        value = int(value)
      kwargs[name] = value
  return kwargs


def to_json_string(obj):
  """Convert object as a JSON string."""
  return json.JSONEncoder(indent=2, encoding='utf-8').encode(obj)


def stringify_enumerated(objs, bullet='*', prefix='', title=None):
  """Produce a string with one object element per line."""
  if not objs:
    return ''

  lines = []
  if title:
    lines.append('{prefix}{title}'.format(prefix=prefix, title=title))
  for value in objs:
    lines.append('{prefix}  {bullet} {value}'.format(
        prefix=prefix, bullet=bullet, value=value))
  return '\n'.join(lines)


class ApiResourceFilter(object):
  """Determines which resources in an API are wanted."""
  # pylint: disable=too-few-public-methods

  def __init__(self, include_regexs, exclude_regexs):
    """Constructor.

    Args:
      include_regexs: [list of re] Regexes to include.
      exclude_regexes: [list of re] Regexes to subtract from include.
    """
    self.__include = include_regexs
    self.__exclude = exclude_regexs

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


class Explorer(object):
  """Explores APIs to see what resources they manage and how to inspect them."""

  @property
  def options(self):
    """Command line options."""
    return self.__options

  @staticmethod
  def collect_apis():
    """Collect names and current versions of all the Google APIs."""
    context = ExecutionContext()
    agent = GcpAgent.make_agent(api='discovery', version='v1')
    apis = agent.list_resource(context, 'apis')

    catalog = {}
    for entry in apis:
      preferred = entry.get('preferred', True)
      if not preferred:
        continue
      catalog[entry['name']] = entry['version']
    return catalog

  def __init__(self, options):
    self.__options = options

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

  def stringify_api(self, api, listable, unlistable, scope_map):
    """Print API to stdout."""
    lines = ['API:  "{api}"'.format(api=api)]
    if unlistable:
      lines.append('  UNLISTABLE')
      for name in unlistable:
        lines.append('    * {0}'.format(name))

    for scope, resource_list in scope_map.items():
      lines.append('  {0}'.format(scope))
      for name in resource_list:
        lines.append('    * {0}: params=({1})'.format(
            name,
            ', '.join([key
                       for key in self.determine_required_parameters(
                           listable[name]).keys()])))
    lines.append('-' * 40 + '\n')
    return '\n'.join(lines)


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


class ApiDiff(object):
  """Contains the resource differences within a given API family."""

  @staticmethod
  def make_api_resources_diff_map(before, after, api_to_resource_filter):
    """Compare a suite of API ResourceLists to another.

    Args:
      before: [dict] Baseline map of {api: {resource: ResourceList}}
      after: [dict] Comparision map of {api: {resource: ResourceList}}
      api_to_resource_filter: [dict] {api: ResourceFilter}
    """
    before_apis = set([api for api in before.keys()
                       if api_to_resource_filter.get(api)])
    after_apis = set([api for api in after.keys()
                      if api_to_resource_filter.get(api)])

    return {api: ApiDiff(before.get(api), after.get(api),
                         api_to_resource_filter.get(api))
            for api in before_apis.union(after_apis)}

  def __init__(self, before, after, resource_filter):
    """Compare all ResourceLists within an API.

    Args:
      api: [string] The API name.
      before: [dict] Map of resource name to ResourceList for baseline.
      after: [dict] Map of resource name to ResourceList for comparison.
      resource_filter: [ResourceFilter] Determines resource names to match.
    """
    self.__errors = []
    self.__resource_diffs = {}
    before_keys = set([key for key in before.keys()
                       if resource_filter.wanted(key)])
    after_keys = set([key for key in after.keys()
                      if resource_filter.wanted(key)])
    removed_tuples = [
        (key, stringify_enumerated(before[key].response, title=None,
                                   prefix='    ', bullet='+'))
        for key in before_keys.difference(after_keys)]

    added_tuples = [
        (key, stringify_enumerated(after[key].response, title=None,
                                   prefix='    ', bullet='+'))
        for key in after_keys.difference(before_keys)]
    resources_removed = (
        ['{key}\n{values}'.format(
            key=data[0], values=data[1]) for data in removed_tuples]
        if removed_tuples else [])
    resources_added = (
        ['{key}\n{values}'.format(
            key=data[0], values=data[1]) for data in added_tuples]
        if added_tuples else [])

    if resources_removed:
      self.__errors.append(stringify_enumerated(
          resources_removed, title='MISSING RESOURCES', prefix=''))
    if resources_added:
      self.__errors.append(stringify_enumerated(
          resources_added, title='EXTRA RESOURCES', prefix=''))

    self.__resource_diffs = {
        resource: _ApiResourceDiff(resource,
                                   before[resource], after[resource])
        for resource in before_keys.intersection(after_keys)}

  def stringify(self, show_same):
    """Render as string with or without the equivalent items."""
    result = list(self.__errors)
    for value in sorted(self.__resource_diffs.values(),
                        key=lambda value: value.resource):
      value_str = value.stringify(show_same)
      if value_str:
        result.append(value_str)

    return '  ' + '\n  '.join(result) if result else ''


class _ApiResourceDiff(object):
  """Compare resource lists."""

  @property
  def resource(self):
    """The resource being diffed."""
    return self.__resource

  def __init__(self, resource, before, after):
    """Constructor.

    Args:
      resource: [string] The name of the resource.
      before: [ResourceList] The baseline snapshot.
      after: [ResourceList] The snapshot to compare.
    """
    self.__before = before
    self.__after = after
    self.__resource = resource
    self.__removed = []
    self.__added = []
    self.__same = []
    self.__error = None

    if before.params != after.params:
      self.__error = (
          'PARAMETERS for "{resource}" DIFFER so values are disjoint\n'
          '  Before: {before}\n'
          '  After : {after}'
          .format(resource=resource, before=before.params, after=after.params))
      return

    before_names = set(before.response)
    after_names = set(after.response)
    self.__removed = before_names.difference(after_names)
    self.__added = after_names.difference(before_names)
    self.__same = before_names.intersection(after_names)

  def stringify(self, show_same):
    """Render as string with or without the equivalent items."""
    if self.__error:
      return self.__error

    result = []
    bindings = ', '.join(['{0}={1}'.format(name, value)
                          for name, value in self.__before.params.items()])
    indent = ''
    if self.__added or self.__removed or show_same:
      result.append(
          'RESOURCE: {0}({1})  +/-/= {2}/{3}/{4}'.format(
              self.__resource, bindings,
              len(self.__added), len(self.__removed), len(self.__same)))
      indent += '  '
    elif len(self.__removed) + len(self.__added) + len(self.__same) == 0:
      if show_same and self.__resource:
        result.append(
            '{0}RESOURCE: {1}({2})  empty'.format(
                indent, self.__resource, bindings))

    if self.__added:
      result.append(
          stringify_enumerated(self.__added, bullet='+', prefix=indent))
    if self.__removed:
      result.append(
          stringify_enumerated(self.__removed, bullet='-', prefix=indent))

    if self.__same and show_same:
      result.append(
          stringify_enumerated(self.__same, bullet='=', prefix=indent))

    return '\n'.join(result) if result else ''


class Processor(object):
  """Functions for performing heuristics on APIs and resources."""

  @property
  def explorer(self):
    """The bound explorer helper class."""
    return self.__explorer

  @property
  def default_variables(self):
    """Default variables to use where needed by API methods."""
    return self.__default_variables

  def __init__(self, explorer):
    options = explorer.options
    bindings_kwargs = binding_string_to_dict(options.bindings)
    in_project = bindings_kwargs.get('project', options.project)
    for which in ['project', 'projectId']:
      if not bindings_kwargs.get(which):
        if not in_project:
          try:
            in_project = get_metadata('project/project-id')
          except IOError:
            continue
        bindings_kwargs[which] = in_project

    self.__explorer = explorer
    self.__options = options
    self.__default_variables = bindings_kwargs

  def make_agent(self, api, version, default_scope, default_variables=None):
    """Construct an agent to talk to a Google API.

    Args:
      api: [string] The API name containing the resources.
      version: [string] The API version.
      default_scope: [string] The OAuth scope to use.
         This is only considered if given an options.credentials_path.
    """
    credentials = self.__options.credentials_path or None
    default_variables = default_variables or self.__default_variables
    scope_list = [default_scope] if credentials else None
    return GcpAgent.make_agent(
        api=api, version=version,
        scopes=scope_list,
        credentials_path=credentials,
        default_variables=default_variables)

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
        error = err.message
        # Maybe try again if more remaining.

    if re.search(r"missing required parameters.*\[u?'zone'\]", error):
      return LIST_BY_ZONE, None, None
    elif re.search(r"missing required parameters.*\[u?'region'\]", error):
      return LIST_BY_REGION, None, None

    return None, None, error

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

    if method_name == LIST_BY_ZONE:
      param_name = 'zone'
      param_variants = get_all_zones()
    elif method_name == LIST_BY_REGION:
      param_name = 'region'
      param_variants = get_all_regions()
    else:
      params = agent.resource_method_to_variables(method_name, resource)
      return ListedResources(
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

    return ListedResources(params, 'aggregatedList', items)

  def list_api(self, api, version, scope_map, item_filter=None):
    """List the instances of an API."""
    result = {}
    errors = {}

    for scope, resource_list in scope_map.items():
      try:
        agent = self.make_agent(api, version, scope)
      except HttpError as err:
        print ('E Could not create agent'
               'for "{0}" {1} with scope={2}: {3}'
               .format(api, version, scope, err.message))
        continue

      for resource in resource_list:
        method_name, transform, error_msg = (
            self.__determine_list_method_and_transform(agent, resource))
        if method_name is None:
          errors[resource] = error_msg
          continue

        try:
          params, method_name, instances = self.__list_resource_helper(
            agent, method_name, resource, transform)
          if item_filter:
            if method_name == 'aggregatedList':
              instances = [item for item in instances if item_filter(item[1])]
            else:
              instances = [item for item in instances if item_filter(item)]
        except (TypeError, ValueError, HttpError) as err:
          print '*** ' + str(err)
          errors[resource] = err.message
          continue

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

        result[resource] = resource_list

    return result, errors

  def __determine_added_instances(self, resource, before, after):
    """Determine the resource instances added to |after| since |before|.
    """
    if resource in before:
      if before[resource].params != after[resource].params:
        print ('WARNING: ignoring "{0}" because parameters do not match.'
               .format(resource))
        return []

      before_values = set(before[resource].response)
      after_values = set(after[resource].response)
      return after_values.difference(before_values)
    else:
      return set(after[resource].response)

  def delete_all_collected(
      self, resource_type, discovery_doc, collected, bindings):
    """Delete all the collected items.

    Args:
      resource_type: The API resource type of the items must be homogenous.
      discovery_doc: The API discovery document.
      collected: The API resource items as collected from the API.
        If an aggregated_list() method was used, then this is a tuple that
        also includes the key from the list needed by the delete() method.
      bindings: The bindings to use for variables needed by delete. If
        this is none, use processor's default variables.
    """
    api, version = discovery_doc['id'].split(':')
    resource_container = discovery_doc.get('resources')
    resource_segments = resource_type.split('.')
    resource_spec = {}
    for segment in resource_segments:
      resource_spec = resource_container.get(segment, {})
      resource_container = resource_spec.get('resources', {})

    delete = resource_spec.get('methods', {}).get('delete', None)
    if not delete:
      print '*** Cannot find delete method for "{0}"'.format(resource_type)
      return None

    scope = self.__explorer.pick_scope(
        delete.get('scopes', []), api, mutable=True)
    agent = self.make_agent(api, version, scope,
                            default_variables=bindings)

    if collected:
      action = 'PREVIEWING' if self.__options.dry_run else 'DELETING'
      print '\n{action} from API={api} with scope={scope}'.format(
          action=action,
          api=api,
          scope=scope if self.__options.credentials_path else '<default>')

      sample = collected.pop()
      was_aggregated = isinstance(sample, tuple)
      collected.add(sample)
    else:
      was_aggregated = False

    return AttemptedResourceDeletes(
        agent, was_aggregated,
        self.__try_delete_all(
            agent, resource_type, collected, was_aggregated))

  def delete_added(self, api, version, before, after, resource_filter):
    """Delete resources that were added since the baseline.

    Args:
      api: [string] The API name containing the resources.
      version: [string] The API version.
      before: [dict] {resource: [ResourceList]} baseline.
      after: [dict] {resource: [ResourceList]} changed.
      resource_filter: [ResourceFilter] Determines resource names to consider.
    """
    if resource_filter is None:
      return

    discovery_doc = GcpAgent.download_discovery_document(
        api=api, version=version)

    common_resource_types = set([
        resource_type
        for resource_type in set(before.keys()).intersection(set(after.keys()))
        if resource_filter.wanted(resource_type)])
    added_resource_types = set([
        resource_type
        for resource_type in set(after.keys()).difference(before.keys())
        if resource_filter.wanted(resource_type)])
    resource_types_to_consider = common_resource_types.union(
        added_resource_types)

    all_results = {}
    for resource_type in resource_types_to_consider:
      added = self.__determine_added_instances(resource_type, before, after)
      if not added:
        continue

      type_results = self.delete_all_collected(
          resource_type, discovery_doc, added, after[resource_type].params)
      if type_results:
        all_results[resource_type] = type_results

    self.wait_for_delete_and_maybe_retry(all_results)
    print '-' * 40 + '\n'

  def wait_for_delete_and_maybe_retry(self, waiting_on):
    """Wait for outstanding results to finish deleting.

    If some elements were conflicted, then retry them as long as we made some
    progress since the last retry (by successful deletes).
    """
    while waiting_on:
      retryable_elems = {}
      for resource_type, agent_results in waiting_on.items():
        agent = agent_results[0]
        aggregated = agent_results[1]
        results = agent_results[2]
        result = self.__wait_on_delete(
            agent, resource_type, results, aggregated)
        if result:
          retryable_elems[resource_type] = (agent, aggregated, result)
      waiting_on = {}
      if retryable_elems:
        print 'Retrying some failures that are worth trying again.'
        for resource_type, data in retryable_elems.items():
          agent = data[0]
          aggregated = data[1]
          elems = data[2]
          waiting_on[resource_type] = AttemptedResourceDeletes(
              agent, aggregated, self.__try_delete_all(
                  agent, resource_type, elems, aggregated))

  def __wait_on_delete(
        self, agent, resource_type, results, aggregated, timeout=180):
    """Wait for outstanding results to finish deleting or timeout."""
    awaiting_list = results.get(httplib.OK, [])
    retryable_elems = []
    for code in _RETRYABLE_DELETE_HTTP_CODES:
      retryable_elems.extend(results.get(code, []))

    # Wait for the deletes to finish before returning
    wait_until = time.time() + timeout
    print_every_secs = 20
    approx_secs_so_far = 0   # used to print every secs
    if awaiting_list:
      print 'Waiting for {0} items to finish deleting ...'.format(
        len(awaiting_list))

      while awaiting_list and time.time() < wait_until:
        awaiting_list = [elem for elem in awaiting_list
                         if self.__elem_exists(agent, resource_type,
                                               elem, aggregated)]
        if awaiting_list:
          sleep_secs = 5
          approx_secs_so_far += sleep_secs
          if approx_secs_so_far % print_every_secs == 0:
            print '  Still waiting on {0} ...'.format(len(awaiting_list))
          time.sleep(sleep_secs)
      if awaiting_list:
        print 'Gave up waiting on remaining {0} items.'.format(
            len(awaiting_list))

    return retryable_elems

  def __elem_exists(self, agent, resource_type, elem, aggregated):
    """Determine if a pending delete on an instance has completed or not."""
    context = ExecutionContext()
    params = {}
    if aggregated:
      name = elem[1]
      param_name, param_value = elem[0].split('/', 1)
      if param_name[-1] == 's':
        param_name = param_name[:-1]

      # Just because the aggregation returned a parameter
      # does not mean the get API takes it. Confirm before adding.
      if (agent.resource_type_to_discovery_info(resource_type)
          .get('methods', {}).get('get', {}).get('parameters', {})
          .get(param_name)):
        params[param_name] = param_value

    name = elem[1] if aggregated else elem
    try:
      agent.get_resource(context, resource_type, resource_id=name, **params)
      return True
    except HttpError as http_error:
      if http_error.resp.status == httplib.NOT_FOUND:
        return False
      if http_error.resp.status in _RETRYABLE_DELETE_HTTP_CODES:
        return True
      print 'Unexpected error while waiting for delete: {0} {1}={2}'.format(
        resource_type, name, http_error)
    return False

  def __try_delete_all(
        self, agent, resource_type, results_to_delete, aggregated):
    """Implements the actual delete heuristics.

    Args:
      agent: [GcpAgent] The agent to delete the resources.
      resource_type: [string] The resource type to delete.
      results_to_delete: [string] The listing results to be deleted.
         These may be the ids or may be tuples (params, result) if
         the listing was an aggreatedList.
      aggregated: [bool] Indicates whether results_to_delete were aggregated.
    """
    context = ExecutionContext()
    result_by_code = {}
    for elem in results_to_delete:
      params = {}
      name = elem
      if aggregated:
        name = elem[1]
        try:
          param_name, param_value = elem[0].split('/', 1)
        except ValueError as vex:
          print 'Ignoring error {0}'.format(vex)
          print '   type={0}, name={1}: ELEM[0] was {2!r}'.format(
            resource_type, name, elem[0])
          continue

        if param_name[-1] == 's':
          param_name = param_name[:-1]

        # Just because the aggregation returned a parameter
        # does not mean the delete API takes it. Confirm before adding.
        if (agent.resource_type_to_discovery_info(resource_type)
            .get('methods', {}).get('delete', {}).get('parameters', {})
            .get(param_name)):
          params[param_name] = param_value

      name = elem[1] if aggregated else elem
      try:
        if self.__options.dry_run:
          variables = agent.resource_method_to_variables(
              'delete', resource_type, resource_id=name, **params)
          args_str = ','.join([' {0}={1!r}'.format(key, value)
                               for key, value in variables.items()])

          print '[dry run] delete "{type}" {name} {args}'.format(
              type=resource_type, name=name, args=args_str)
        else:
          agent.invoke_resource(context, 'delete', resource_type,
                                resource_id=name, **params)
          print 'Deleted "{type}" {name}'.format(
              type=resource_type, name=name)

        if httplib.OK in result_by_code:
          result_by_code[httplib.OK].append(elem)
        else:
          result_by_code[httplib.OK] = [elem]
      except HttpError as http_error:
        if http_error.resp.status in result_by_code:
          result_by_code[http_error.resp.status].append(elem)
        else:
          result_by_code[http_error.resp.status] = [elem]

        if http_error.resp.status == httplib.NOT_FOUND:
          print '  - "{type}" "{name}" was already deleted'.format(
              type=resource_type, name=name)
        else:
          print ('  Ignoring error deleting "{type}" "{name}": {msg}'
                 .format(type=resource_type, name=name, msg=http_error))
      except ValueError as value_error:
        # NOTE(ewiseblatt): 20170928
        # This is a quick fix because instanceGroupManagers.aggregatedList
        # is returning some regions but the delete only takes zones. The
        # region results are missing the zone value. Ignore those errors.
        # This isnt the best place to handle this, but is the easiest for
        # now and I dont have time to devise a cleaner solution right now.
        print 'Ignoring error with "delete {0} {1} {2}": {3}'.format(
            resource_type, name, params, value_error)
        if -1 in result_by_code:
          result_by_code[-1].append(elem)
        else:
          result_by_code[-1] = [elem]

    return result_by_code if self.__options.delete_for_real else {}


class Main(object):
  """Implements command line program for producing and manipulating snapshots.
  """

  @staticmethod
  def __get_options():
    """Determine commandline options."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'apis', nargs='+',
        help='The list of APIs to process. These can be in the form'
             ' <api>.<resource> to limit particular resources.'
             ' The <resource> can have "*" wildcards.')

    parser.add_argument(
        '--catalog', default=False, action='store_true',
        help='Show a catalog of all the listable resources.')
    parser.add_argument(
        '--print_api_spec', default=False, action='store_true',
        help='Print the discovery document for the API itself.')

    parser.add_argument(
        '--exclude', default='',
        help='A command-separated list of resources to exclude. These'
             ' are subtracted from the api list of resources to include.')

    parser.add_argument(
        '--project', default=None,
        help='The project owning the resources to consider.'
             ' This should only be specified if the resource API requires a'
             ' project (e.g. compute.images, but not storage.objects).'
             ' An empty string means the local GCP project.'
             '\nThis is a shortcut for adding the project into --bindings'
             ' as either "project" or "projectId".')

    parser.add_argument(
        '--bindings', default=None,
        help='A comma-separated list of variable bindings where a binding is'
             ' <name>=<value>. Used as parameters as needed with API methods.')
    parser.add_argument(
        '--credentials_path', default='',
        help='Path to overide credentials from JSON file.')

    parser.add_argument(
        '--list', default=False, action='store_true',
        help='List the resource instances.')
    parser.add_argument('--name', default=None,
        help='The regular expression for resource instance names to include.'
             ' The default is none (dont consider)')
    parser.add_argument(
        '--days_before', default=None, type=int,
        help='The number of recent days to exclude (exclusive).'
             ' The default is none (dont consider)')
    parser.add_argument(
        '--days_since', default=None, type=int,
        help='The number of recent days to include (inclusive).'
             ' The default is none (dont consider)')

    parser.add_argument(
        '--output_path', default=None,
        help='Store listing results to file.')
    parser.add_argument(
        '--compare', default=None, nargs=2,
        help='Compare two stored result files.')
    parser.add_argument(
        '--show_unchanged', default=False, action='store_true',
        help='Also show unchanged values in listing compare.')
    parser.add_argument(
        '--delete_added', default=False, action='store_true',
        help='Delete the added resources after --compare.')
    parser.add_argument(
        '--delete_list', default=False, action='store_true',
        help='Delete the specified resources.')

    parser.add_argument('--dry_run', default=False, action='store_true',
        help='Show proposed changes (deletes), dont actually perform them.')

    parser.add_argument(
        '--delete_for_real', default=False, action='store_true',
        help='DEPRECATED')

    return parser.parse_args()

  @property
  def exit_code(self):
    """Return the exit code."""
    return self.__exit_code

  @property
  def processor(self):
    """The bound processor helper class."""
    return self.__processor

  @staticmethod
  def __determine_age_date_str(days_ago):
    """Determine the date string for the given age (in days)."""
    now = datetime.datetime.now()
    today = datetime.datetime(now.year, now.month, now.day)
    return ((today - datetime.timedelta(days_ago)).isoformat()
            if days_ago is not None
            else None)

  @staticmethod
  def make_item_filter(options):
    """Create filter from options for filtering out resource items.

    Args:
       options: [argparse namespace] See command line options.
    """
    name_regex = re.compile('^' + options.name + '$') if options.name else None
    before_str = Main.__determine_age_date_str(options.days_before)
    since_str = Main.__determine_age_date_str(options.days_since)

    def determine_timestamp(item):
      """Figure out appropriate item timestamp for filtering."""
      # There is no standard for this.
      # The following are common to some APIs.
      for key in ['creationTimestamp', 'timeCreated']:
        if key in item:
          return item[key]

      error = 'Could not determine timestamp key for {0}'.format(
          item.get('kind', item))
      print error
      raise ValueError(error)

    def item_filter(item):
      """Apply option filters to an API resource item."""
      if name_regex:
        name = None
        for key in ['name', 'id']:
          name = item.get(key)
          if name is not None:
            break
        if name is None:
          print 'Could not determine name for {0}'.format(item)
          return False
        if not name_regex.match(name):
          return False

      if before_str:
        try:
          if determine_timestamp(item) >= before_str:
            return False
        except ValueError:
          pass

      if since_str:
        try:
          if determine_timestamp(item) < since_str:
            return False
        except ValueError:
          pass
      return True

    return item_filter


  def __init__(self, options):
    self.__item_filter = self.make_item_filter(options)
    self.__options = options
    self.__explorer = Explorer(options)
    self.__processor = Processor(self.__explorer)
    self.__version_map = None
    self.__aggregated_listings = {}
    self.__listable_unlistable_scope_cache = {}
    self.__api_to_resource_filter_map = {}
    self.__exit_code = 0

  @property
  def version_map(self):
    """Returns map of API name to current version."""
    if self.__version_map is None:
      self.__version_map = Explorer.collect_apis()
    return self.__version_map

  @property
  def api_to_resource_filter_map(self):
    return self.__api_to_resource_filter_map

  @api_to_resource_filter_map.setter
  def api_to_resource_filter_map(self, api_resource_filter_map):
    self.__api_to_resource_filter_map = api_resource_filter_map

  @staticmethod
  def main():
    """Runs the command-line program."""
    program = Main(Main.__get_options())

    # Set global agent for lazy evaluation of zones and regions if we need.
    # We do this here because we need the credentials.
    global _compute_agent
    _compute_agent = program.__processor.make_agent(
        'compute', 'v1', 'https://www.googleapis.com/auth/compute.readonly')

    program.run()
    return program.exit_code

  @staticmethod
  def make_apis_to_resource_filter_map(api_list):
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

  def run(self):
    """Run the commandline program."""
    apis = self.__options.apis
    if apis == ['all']:
      apis = self.version_map.keys()

    api_to_include_map = self.make_apis_to_resource_filter_map(apis)
    api_to_exclude_map = self.make_apis_to_resource_filter_map(
        self.__options.exclude.split(',')
        if self.__options.exclude else [])

    bad_apis = [api for api in api_to_include_map.keys()
                if not api in self.version_map]
    bad_apis.extend([api for api in api_to_exclude_map.keys()
                     if not api in self.version_map])
    if bad_apis:
      print 'Unknown apis: {0}'.format(', '.join(['"{0}"'.format(s)
                                                  for s in bad_apis]))
      self.__exit_code = -1
      return

    self.api_to_resource_filter_map = {
        api: ApiResourceFilter(api_to_include_map[api],
                               api_to_exclude_map.get(api) or [])
        for api in api_to_include_map.keys()}

    self.process_commands()

  def process_commands(self):
    """Run all the commands."""
    if self.__options.catalog:
      self.__foreach_api(self.do_command_print_catalog)

    if self.__options.print_api_spec:
      self.__foreach_api(self.do_command_print_api_spec)

    if self.__options.list:
      self.__foreach_api(self.do_command_collect_api)

    if self.__options.delete_list:
      self.__foreach_api(self.do_command_delete_list)

    options = self.__options
    if options.output_path and self.__aggregated_listings:
      with open(options.output_path, 'wb+') as sink:
        pickler = pickle.Pickler(sink)
        pickler.dump(self.__aggregated_listings)

    before = None
    after = None
    num_diffs = 0
    if options.compare:
      with open(options.compare[0], 'rb') as source:
        unpickler = pickle.Unpickler(source)
        before = unpickler.load()
      with open(options.compare[1], 'rb') as source:
        unpickler = pickle.Unpickler(source)
        after = unpickler.load()
      num_diffs = self.__do_compare_snapshots(before, after)

    if options.delete_added:
      for api in set(before.keys()).intersection(after.keys()):
        self.__processor.delete_added(
            api, self.version_map[api], before[api], after[api],
            self.__api_to_resource_filter_map.get(api))
    elif num_diffs != 0:
      self.__exit_code = 1

  def __foreach_api(self, func):
    """Execute a function for each api name of interest."""
    return {api: func(api) for api in self.__api_to_resource_filter_map.keys()}

  def __get_listable_unlistable_scope_map(self, api):
    """Determine the listable and unlistable methods and the scope to use."""
    if api not in self.__listable_unlistable_scope_cache:
      version = self.version_map[api]
      listable, unlistable = self.__explorer.find_listable_resources(
          api, version, self.__api_to_resource_filter_map[api])
      scope_map = self.__explorer.determine_scope_map(listable, api)
      self.__listable_unlistable_scope_cache[api] = (listable, unlistable,
                                                     scope_map)
    return self.__listable_unlistable_scope_cache[api]

  def do_command_print_catalog(self, api):
    """Print all the listable (and non-listable) resources of the api."""
    listable, unlistable, scope_map = (
        self.__get_listable_unlistable_scope_map(api))
    text = self.__explorer.stringify_api(api, listable, unlistable, scope_map)
    print text
    return text

  def do_command_print_api_spec(self, api):
    """Print the list method specification for each of the API resources."""
    # pylint: disable=unused-variable
    listable, unlistable, scope_map = (
        self.__get_listable_unlistable_scope_map(api))
    text = '\n'.join(['LISTABLE Resources for {api}'.format(api=api),
                      to_json_string(listable)])
    print text
    return text

  def do_command_collect_api(self, api):
    """Collect all the instances of each of the api resources."""
    # pylint: disable=unused-variable
    listable, unlistable, scope_map = (
        self.__get_listable_unlistable_scope_map(api))
    version = self.version_map[api]

    print 'API:  "{0}"'.format(api)
    found, errors = self.__processor.list_api(api, version, scope_map,
                                              item_filter=self.__item_filter)
    for resource, resource_list in found.items():
      if resource_list.response:
        print resource_list.stringify(resource)

    if errors:
      print 'ERRORS:{0}'.format(
          ''.join(['\n  E {0} {1}'.format(resource, msg)
                   for resource, msg in errors.items()]))

    self.__aggregated_listings[api] = found
    return found

  def do_command_delete_list(self, api):
    """Delete all the specified instances of each of the api resources."""
    resource_type = api
    results = {}
    collected = self.do_command_collect_api(api)
    for resource_type, data in collected.items():
      elems = set(data.response)
      discovery_doc = GcpAgent.download_discovery_document(api=api)
      results[resource_type] = self.processor.delete_all_collected(
          resource_type, discovery_doc, elems, bindings=None)

    self.processor.wait_for_delete_and_maybe_retry(results)

  def __do_compare_snapshots(self, before, after):
    """Print difference between snapshots.

    Args:
      before[dictionary of list results]: The baseline resources keyed by api.
      after[dictionary of list results]: The resources to compare keyed by api.

    Returns:
      The number of different resources (to know if anything was different).
    """

    options = self.__options
    num_diff_apis = 0
    api_diffs = ApiDiff.make_api_resources_diff_map(
        before, after, self.__api_to_resource_filter_map)
    for api, diff in api_diffs.items():
      content = diff.stringify(options.show_unchanged)
      if content:
        num_diff_apis += 1
        if num_diff_apis == 1:
          print 'Differences between snapshots "{0}" and "{1}":'.format(
              *options.compare)
        print '\nAPI "{0}"'.format(api)
        print content
        print '-' * 40
    if num_diff_apis == 0:
      print 'Snapshots "{0}" and "{1}" are equivalent.'.format(
          *options.compare)
    return num_diff_apis


if __name__ == '__main__':
  exit(Main.main())
