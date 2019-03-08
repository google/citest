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

# pylint: disable=too-many-lines

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

from googleapiclient.errors import HttpError

from citest.gcp_testing.gcp_agent import GcpAgent
from citest.base import ExecutionContext
from citest.gcp_testing.api_investigator import ApiInvestigatorBuilder
from citest.gcp_testing.api_resource_scanner import ApiResourceScanner
from citest.gcp_testing.api_resource_diff import ApiDiff


AttemptedResourceDeletes = collections.namedtuple(
    'AttemptedResourcesDeletes', ['agent', 'aggregated', 'code_to_results'])


def to_json_string(obj):
  """Convert object as a JSON string."""
  return json.JSONEncoder(indent=2).encode(obj)


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


class Actuator(object):
  """Functions for performing heuristics on APIs and resources."""

  # When deleting, these errors indicate a possible transient error
  __RETRYABLE_DELETE_HTTP_CODES = [httplib.CONFLICT,
                                   httplib.SERVICE_UNAVAILABLE]

  @property
  def investigator(self):
    """The bound investigator helper class."""
    return self.__investigator

  def __init__(
      self, scanner, credentials_path=None, dry_run=False):
    self.__scanner = scanner
    self.__investigator = scanner.investigator
    self.__dry_run = dry_run
    self.__credentials_path = credentials_path

  def __determine_added_instances(self, resource, before, after):
    """Determine the resource instances added to |after| since |before|.
    """
    if resource in before:
      if before[resource].params != after[resource].params:
        print('WARNING: ignoring "{0}" because parameters do not match.'
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
        this is none, use actuator's default variables.
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
      print('*** Cannot find delete method for "{0}"'.format(resource_type))
      return None

    scope = self.__investigator.pick_scope(
        delete.get('scopes', []), api, mutable=True)
    agent = self.__scanner.make_agent(api, scope, default_variables=bindings)

    if collected:
      action = 'PREVIEWING' if self.__dry_run else 'DELETING'
      print('\n{action} from API={api} with scope={scope}'.format(
          action=action,
          api=api,
          scope=scope))

      sample = collected.pop()
      was_aggregated = isinstance(sample, tuple)
      collected.add(sample)
    else:
      was_aggregated = False

    return AttemptedResourceDeletes(
        agent, was_aggregated,
        self.__try_delete_all(
            agent, resource_type, collected, was_aggregated))

  def delete_added(self, api, before, after, resource_filter):
    """Delete resources that were added since the baseline.

    Args:
      api: [string] The API name containing the resources.
      before: [dict] {resource: [ResourceList]} baseline.
      after: [dict] {resource: [ResourceList]} changed.
      resource_filter: [ResourceFilter] Determines resource names to consider.
    """
    if resource_filter is None:
      return

    discovery_doc = GcpAgent.download_discovery_document(api=api)

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
    print('-' * 40 + '\n')

  def wait_for_delete_and_maybe_retry(self, waiting_on):
    """Wait for outstanding results to finish deleting.

    If some elements were conflicted, then retry them as long as we made some
    progress since the last retry (by successful deletes).
    """
    if self.__dry_run:
      return
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
        print('Retrying some failures that are worth trying again.')
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
    for code in self.__RETRYABLE_DELETE_HTTP_CODES:
      retryable_elems.extend(results.get(code, []))

    # Wait for the deletes to finish before returning
    wait_until = time.time() + timeout
    print_every_secs = 20
    approx_secs_so_far = 0   # used to print every secs
    if awaiting_list:
      print('Waiting for {0} items to finish deleting ...'.format(
          len(awaiting_list)))

      while awaiting_list and time.time() < wait_until:
        awaiting_list = [elem for elem in awaiting_list
                         if self.__elem_exists(agent, resource_type,
                                               elem, aggregated)]
        if awaiting_list:
          sleep_secs = 5
          approx_secs_so_far += sleep_secs
          if approx_secs_so_far % print_every_secs == 0:
            print('  Still waiting on {0} ...'.format(len(awaiting_list)))
          time.sleep(sleep_secs)
      if awaiting_list:
        print('Gave up waiting on remaining {0} items.'.format(
            len(awaiting_list)))

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
      if http_error.resp.status in self.__RETRYABLE_DELETE_HTTP_CODES:
        return True
      print('Unexpected error while waiting for delete: {0} {1}={2}'.format(
          resource_type, name, http_error))

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
          print('Ignoring error {0}'.format(vex))
          print('   type={0}, name={1}: ELEM[0] was {2!r}'.format(
              resource_type, name, elem[0]))
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
        if self.__dry_run:
          variables = agent.resource_method_to_variables(
              'delete', resource_type, resource_id=name, **params)
          args_str = ','.join([' {0}={1!r}'.format(key, value)
                               for key, value in variables.items()])

          print('[dry run] delete "{type}" {name} {args}'.format(
              type=resource_type, name=name, args=args_str))
        else:
          agent.invoke_resource(context, 'delete', resource_type,
                                resource_id=name, **params)
          print('Deleted "{type}" {name}'.format(
              type=resource_type, name=name))

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
          print('  - "{type}" "{name}" was already deleted'.format(
              type=resource_type, name=name))
        else:
          print('  Ignoring error deleting "{type}" "{name}": {msg}'
                .format(type=resource_type, name=name, msg=http_error))
      except ValueError as value_error:
        # NOTE(ewiseblatt): 20170928
        # This is a quick fix because instanceGroupManagers.aggregatedList
        # is returning some regions but the delete only takes zones. The
        # region results are missing the zone value. Ignore those errors.
        # This isnt the best place to handle this, but is the easiest for
        # now and I dont have time to devise a cleaner solution right now.
        print('Ignoring error with "delete {0} {1} {2}": {3}'.format(
            resource_type, name, params, value_error))
        if -1 in result_by_code:
          result_by_code[-1].append(elem)
        else:
          result_by_code[-1] = [elem]

    return result_by_code


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
    parser.add_argument(
        '--name', default=None,
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

    parser.add_argument(
        '--dry_run', default=False, action='store_true',
        help='Show proposed changes (deletes), dont actually perform them.')

    return parser.parse_args()

  @property
  def actuator(self):
    """The bound actuator helper class."""
    return self.__actuator

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
          print('Could not determine name for {0}'.format(item))
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

  def __init__(self, options, scanner):
    self.__scanner = scanner
    self.__investigator = scanner.investigator
    self.__item_filter = self.make_item_filter(options)
    self.__actuator = Actuator(self.__scanner, dry_run=options.dry_run)
    self.__aggregated_listings = {}

  @staticmethod
  def main():
    """Runs the command-line program."""
    options = Main.__get_options()
    builder = ApiInvestigatorBuilder()
    builder.include_apis = options.apis
    builder.exclude_apis = (options.exclude.split(',')
                            if options.exclude else [])
    investigator = builder.build()

    bindings = binding_string_to_dict(options.bindings)
    if options.project and not bindings.get('project'):
      bindings['project'] = options.project

    scanner = ApiResourceScanner(
        investigator, options.credentials_path,
        default_variables=bindings)
    program = Main(options, scanner)
    return program.process_commands(options)

  def process_commands(self, options):
    """Run all the commands."""
    foreach_api = self.__investigator.foreach_api
    if options.catalog:
      foreach_api(self.do_command_print_catalog)

    if options.print_api_spec:
      foreach_api(self.do_command_print_api_spec)

    if options.list:
      foreach_api(self.do_command_collect_api)

    if options.delete_list:
      foreach_api(self.do_command_delete_list)

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
      num_diffs = self.__do_compare_snapshots(options, before, after)

    if options.delete_added:
      for api in set(before.keys()).intersection(after.keys()):
        self.__actuator.delete_added(
            api, before[api], after[api],
            self.__scanner.investigator.get_api_resource_filter(api))

    return num_diffs


  def do_command_print_catalog(self, api):
    """Print all the listable (and non-listable) resources of the api."""
    text = self.__investigator.stringify_api(api, self.__scanner)
    print(text)
    return text

  def do_command_print_api_spec(self, api):
    """Print the list method specification for each of the API resources."""
    listable = self.__scanner.get_listable_api_resources(api)
    text = '\n'.join(['LISTABLE Resources for {api}'.format(api=api),
                      to_json_string(listable)])
    print(text)
    return text

  def do_command_collect_api(self, api):
    """Collect all the instances of each of the api resources."""

    print('API:  "{0}"'.format(api))
    found, errors = self.__scanner.list_api(
        api, item_filter=self.__item_filter)

    for resource, resource_list in found.items():
      if resource_list.response:
        print(resource_list.stringify(resource))

    if errors:
      print('ERRORS:{0}'.format(
          ''.join(['\n  E {0} {1}'.format(resource, msg)
                   for resource, msg in errors.items()])))

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
      results[resource_type] = self.actuator.delete_all_collected(
          resource_type, discovery_doc, elems, bindings=None)

    self.actuator.wait_for_delete_and_maybe_retry(results)

  def __do_compare_snapshots(self, options, before, after):
    """Print difference between snapshots.

    Args:
      before[dictionary of list results]: The baseline resources keyed by api.
      after[dictionary of list results]: The resources to compare keyed by api.

    Returns:
      The number of different resources (to know if anything was different).
    """

    num_diff_apis = 0
    api_diffs = ApiDiff.make_api_resources_diff_map(
        self.__scanner, before, after)
    for api, diff in api_diffs.items():
      content = diff.stringify(options.show_unchanged)
      if content:
        num_diff_apis += 1
        if num_diff_apis == 1:
          print('Differences between snapshots "{0}" and "{1}":'.format(
              *options.compare))
        print('\nAPI "{0}"'.format(api))
        print(content)
        print('-' * 40)
    if num_diff_apis == 0:
      print('Snapshots "{0}" and "{1}" are equivalent.'.format(
          *options.compare))
    return num_diff_apis


if __name__ == '__main__':
  exit(Main.main())
