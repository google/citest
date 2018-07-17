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


"""Diff support for use with ApiResourceScanner"""


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


class ApiResourceDiff(object):
  """Compare resource lists."""

  @property
  def resource(self):
    """The resource being diffed."""
    return self.__resource

  @property
  def added(self):
    """Returns list of added instance names."""
    return self.__added

  @property
  def removed(self):
    """Returns list of removed instance names."""
    return self.__removed

  @property
  def unchanged(self):
    """Returns list of unchanged instance names."""
    return self.__same

  @property
  def error(self):
    """Returns errors found performing the diff, or None"""
    return self.__error

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


class ApiDiff(object):
  """Contains the resource differences within a given API family."""

  @staticmethod
  def make_api_resources_diff_map(scanner, before, after):
    """Compare a suite of API ResourceLists to another.

    Args:
      scanner: [ApiResourceScanner]: scanner for API filtering
      before: [dict] Baseline map of {api: {resource: ResourceList}}
      after: [dict] Comparision map of {api: {resource: ResourceList}}

    Returns:
      map of <api, ApiResourceDiff>
    """
    get_api_resource_filter = scanner.investigator.get_api_resource_filter

    before_apis = set([api for api in before.keys()
                       if get_api_resource_filter(api)])
    after_apis = set([api for api in after.keys()
                      if get_api_resource_filter(api)])
    return {api: ApiDiff(get_api_resource_filter(api),
                         before.get(api), after.get(api))
            for api in before_apis.union(after_apis)}

  @property
  def resources_added(self):
    """Resources types in the AFTER that were not mentioned in the BEFORE.

    These are not necessarily changes among instances, rather denotes
    the precense of information or not.
    """
    return self.__resources_added

  @property
  def resources_removed(self):
    """Resources types in the AFTER that were not mentioned in the BEFORE.

    These are not necessarily changes among instances, rather denotes
    the precense of information or not.
    """
    return self.__resources_removed

  @property
  def resources_diff(self):
    """Resources whose instances have changed between BEFORE and AFTER."""
    return self.__resource_diffs

  def __init__(self, resource_filter, before, after):
    """Compare all ResourceLists within an API.

    Args:
      resource_filter: [ResourceFilter] Determines resource names to match.
      before: [dict] Map of resource name to ResourceList for baseline.
      after: [dict] Map of resource name to ResourceList for comparison.
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
    self.__resources_removed = (
        ['{key}\n{values}'.format(
            key=data[0], values=data[1]) for data in removed_tuples]
        if removed_tuples else [])
    self.__resources_added = (
        ['{key}\n{values}'.format(
            key=data[0], values=data[1]) for data in added_tuples]
        if added_tuples else [])

    if self.__resources_removed:
      self.__errors.append(stringify_enumerated(
          self.__resources_removed,
          title='MISSING RESOURCES',
          prefix=''))
    if self.__resources_added:
      self.__errors.append(stringify_enumerated(
          self.__resources_added,
          title='EXTRA RESOURCES',
          prefix=''))

    self.__resource_diffs = {
        resource: ApiResourceDiff(resource,
                                  before[resource], after[resource])
        for resource in before_keys.intersection(after_keys)}

  def to_instances_added(self):
    """Return map of <resource name, [instance names added]>."""
    return {
        resource: diff.added
        for resource, diff in self.__resource_diffs.items()
        if diff.added
    }

  def to_instances_removed(self):
    """Return map of <resource name, [instance names removed]>."""
    return {
        resource: diff.removed
        for resource, diff in self.__resource_diffs.items()
        if diff.removed
    }

  def stringify(self, show_same):
    """Render as string with or without the equivalent items."""
    result = list(self.__errors)
    for value in sorted(self.__resource_diffs.values(),
                        key=lambda value: value.resource):
      value_str = value.stringify(show_same)
      if value_str:
        result.append(value_str)

    return '  ' + '\n  '.join(result) if result else ''
