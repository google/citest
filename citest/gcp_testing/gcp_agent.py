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

"""Helper functions for creating GCP service agents."""


import json
import logging

import apiclient
import httplib2

from oauth2client.client import GoogleCredentials
from oauth2client.service_account import ServiceAccountCredentials

from citest.base import JournalLogger
from citest.service_testing import BaseAgent
import citest

# This doesnt belong here, but this library insists on logging
# ImportError: file_cache is unavailable when using oauth2client >= 4.0.0
# The maintainer wont fix or remove the warning so we'll force it to be disabled
logging.getLogger('googleapiclient.discovery_cache').setLevel(logging.ERROR)


PLATFORM_READ_ONLY_SCOPE = (
    'https://www.googleapis.com/auth/cloud-platform.read-only'
    )
PLATFORM_FULL_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'


class GcpAgent(BaseAgent):
  """Agent that interacts with services specified by the Discovery API."""

  @classmethod
  def default_discovery_name_and_version(cls):
    """Returns (Discovery Service name, version) for this agent class.

    The service name and version are used to lookup the API discovery document
    for internal implementation details.
    """
    raise NotImplementedError()

  @classmethod
  def download_discovery_document(cls, api=None, version=None):
    """Return the discovery document for the specified service.

    Args:
      api: [string] The API name to use or None for default.
      version: [String] The service API version.
    Returns:
      https://developers.google.com/discovery/v1/reference/apis#resource
    """
    if api is None:
      default_api, default_version = cls.default_discovery_name_and_version()
      api = default_api
      version = version or default_version

    if version is None:
      version = GcpAgent.determine_current_version(api)

    http = httplib2.Http()
    http = apiclient.http.set_user_agent(
        http, 'citest/{version}'.format(version=citest.__version__))
    service = apiclient.discovery.build('discovery', 'v1', http=http)

    # pylint: disable=no-member
    return service.apis().getRest(api=api, version=version).execute()

  @staticmethod
  def determine_current_version(api):
    """Determine current version of Google API

    Args:
      api: [string] Google API name
    """
    discovery = GcpAgent.make_service('discovery', 'v1')
    response = discovery.apis().list(name=api, preferred=True).execute()
    if not response.get('items'):
      raise ValueError('Unknown API "{0}".'.format(api))
    return response['items'][0]['version']

  @classmethod
  def make_service(cls, api=None, version=None,
                   scopes=None, credentials_path=None,
                   logger=None):
    """Instantiate a client service instance.

    Args:
      version: [string] The version of the API to use.
      scopes: [string] List of scopes to authorize, or None.
      credentials_path: [string] Path to json file with credentials, or None.
      logger: [Logger] The logger to inject into the agent if not the default.
    Returns:
      Service
    """
    credentials_path = credentials_path or None
    logger = logger or logging.getLogger(__name__)

    if api is None:
      default_api, default_version = cls.default_discovery_name_and_version()
      api = default_api
      version = version or default_version

    if version is None:
      version = GcpAgent.determine_current_version(api)

    http = httplib2.Http()
    http = apiclient.http.set_user_agent(
        http, 'citest/{version}'.format(version=citest.__version__))
    credentials = None
    if credentials_path is not None:
      logger.info('Authenticating %s %s', api, version)
      credentials = ServiceAccountCredentials.from_json_keyfile_name(
          credentials_path, scopes=scopes)
    else:
      credentials = GoogleCredentials.get_application_default()
      if scopes and credentials.create_scoped_required():
        credentials = credentials.create_scoped(scopes)

    http = credentials.authorize(http)
    logger.info('Constructing %s service...', api)
    return apiclient.discovery.build(api, version, http=http)

  @classmethod
  def make_agent(cls, api=None, version=None,
                 scopes=None, credentials_path=None,
                 default_variables=None,
                 **kwargs):
    """Factory method to create a new agent instance.

    This is a convienence method to create a new instance with standard
    service and discovery document parameters.

    Args:
      api: [string] The API name to use or None for default.
      version: [string] The version of the API to use or None for default.
      scopes: [string] List of scopes to authorize, or None.
      credentials_path: [string] Path to json file with credentials, or None.
      default_variables: [dict] Default variable values to pass to methods.
         These are only used when the method has a parameter that was not
         explicitly provided in the invocation.
      logger: [Logger] The logger to inject if other than the default.
    Returns:
      Agent
    """
    # pylint: disable=too-many-arguments
    if version is None and api is not None:
      version = GcpAgent.determine_current_version(api)

    service = cls.make_service(api, version, scopes, credentials_path)
    discovery_doc = cls.download_discovery_document(api=api, version=version)
    return cls(service, discovery_doc, default_variables, **kwargs)

  @property
  def service(self):
    """The bound service client."""
    return self.__service

  @property
  def discovery_document(self):
    """The Discovery document specifying the bound service."""
    return self.__discovery_doc

  @property
  def default_variables(self):
    """Default variables for method invocations."""
    return self.__default_variables

  def __init__(self, service, discovery_doc, default_variables=None,
               logger=None):
    """Constructor.

    Args:
      service: [Service] The service client instance.
      discovery_doc: [dict] The service's Discovery document.
      default_variables: [dict] Default variable values to pass to methods.
         These are only used when the method has a parameter that was not
         explicitly provided in the invocation.
    """
    logger = logger or logging.getLogger(__name__)
    super(GcpAgent, self).__init__(logger=logger)
    self.__service = service
    self.__discovery_doc = discovery_doc
    self.__default_variables = dict(default_variables or {})
    self.__api_title = discovery_doc['title']
    self.__api_name = discovery_doc['name'].title()

  def resource_method_to_variables(
      self, method, resource_type, resource_id=None, **kwargs):
    """Determine variable bindings to pass to a method.

    Args:
      method: [string] The name of the desired method (in the resource_type).
      resource_type: [string] The resource type operating on.
      resource_id: [string] The particular instance to operate on, if any.
      kwargs: Additional variable bindings

    Returns
      kwargs ammended with additional default variables, if applicable.
    """
    resource_info = self.resource_type_to_discovery_info(resource_type)
    method_spec = resource_info.get('methods', {}).get(method, None)
    if method_spec is None:
      raise KeyError('Unknown method={0} on resource={1}'
                     .format(method, resource_type))
    parameters = method_spec.get('parameters', {})
    result = {key: value for key, value in kwargs.items() if value is not None}
    resource_id_param = None
    if resource_id is not None:
      resource_id_param = method_spec['parameterOrder'][-1]
      result[resource_id_param] = resource_id

    missing = []
    for key, key_spec in parameters.items():
      if key not in kwargs and key != resource_id_param:
        def_value = self.__default_variables.get(key, None)
        if def_value is not None:
          result[key] = def_value
        elif key_spec.get('required', False):
          missing.append(key)

    if missing:
      raise ValueError('"{0}()" is missing required parameters: {1}'
                       .format(method, missing))
    return result

  def get_resource(self, context, resource_type, resource_id=None, **kwargs):
    """Get instance metadata details.

    Args:
      resource_type: [string] The type of the resource instance to get.
      resource_id: [string] The id of the resource instance to get.
      kwargs: [kwargs] Additional parameters may be required depending
         on the resource type (such as zone, etc).
    """
    return self.invoke_resource(
        context, 'get',
        resource_type=resource_type, resource_id=resource_id, **kwargs)

  def invoke_resource(self, context, method, resource_type,
                      resource_id=None, **kwargs):
    """Invoke a method on a resource type or instance.

    Args:
      method: [string] The operation to perform as named under the
          |resource_type| in the discovery document.
      resource_type: [string] The type of the resource instance to operate on.
      resource_id: [string] The id of the resource instance, or None to operate
        on the resource type or collection.
      kwargs: [kwargs] Additional parameters may be required depending
         on the resource type and method.
    """
    return JournalLogger.execute_in_context(
        'Invoke "{method}" {type}'.format(method=method, type=resource_type),
        lambda: self.__do_invoke_resource(
            context, method, resource_type,
            resource_id=resource_id, **kwargs))

  def __do_invoke_resource(self, context, method, resource_type,
                           resource_id=None, **kwargs):
    """Implements invoke_resource()."""
    variables = self.resource_method_to_variables(
        method, resource_type, resource_id=resource_id, **kwargs)
    variables = context.eval(variables)

    resource_obj = self.resource_type_to_resource_obj(resource_type)
    logging.debug('Calling %s.%s', resource_type, method)
    JournalLogger.journal_or_log(
        'Requesting {type} {method} {vars}'.format(
            type=resource_type, method=method, vars=variables),
        _logging=self.logger.name,
        _context='request')

    request = getattr(resource_obj(), method)(**variables)
    response = request.execute()
    JournalLogger.journal_or_log(
        json.JSONEncoder(separators=(',', ': ')).encode(response),
        _logger=self.logger, _context='response', format='json')

    return response

  def list_resource(self, context, resource_type, method_variant='list',
                    item_list_transform=None, **kwargs):
    """List the contents of the specified resource.

    Args:
      resource_type: [string] The name of the resource to list.
      method_variant: [string] The API method name to invoke.
      item_list_transform: [lambda items] Converts the list of items into
         a result list, or None for the identity.
      kwargs: [kwargs] Additional parameters may be required depending
         on the resource type (such as zone, etc).

    Returns:
      A list of resources.
    """
    return JournalLogger.execute_in_context(
        'List {}'.format(resource_type),
        lambda: self.__do_list_resource(
            context, resource_type, method_variant=method_variant,
            item_list_transform=item_list_transform, **kwargs))

  def __do_list_resource(self, context, resource_type, method_variant='list',
                         item_list_transform=None, **kwargs):
    """Helper function implementing list_resource()."""
    resource_obj = self.resource_type_to_resource_obj(resource_type)
    method_container = resource_obj()
    variables = self.resource_method_to_variables(
        method_variant, resource_type, **kwargs)
    variables = context.eval(variables)
    request = getattr(method_container, method_variant)(**variables)

    all_objects = []
    more = ''
    while request:
      logging.debug('Calling %s.%s', resource_type, method_variant,
                    extra={'citest_journal':{'nojournal':True}})
      JournalLogger.journal_or_log(
          'Listing {0}{1}'.format(more, resource_type),
          _logger=self.logger, _context='request')
      response = request.execute()
      JournalLogger.journal_or_log(
          json.JSONEncoder(separators=(',', ': ')).encode(response),
          _logger=self.logger, _context='response', format='json')

      response_items = response.get('items', None)
      if response_items is None:
        # Assume item reponse is named by the type being listed.
        response_items = response.get(resource_type.split('.')[-1], [])

      all_items = (item_list_transform(response_items)
                   if item_list_transform
                   else response_items)
      if not isinstance(all_items, list):
        all_items = [all_items]
      all_objects.extend(all_items)
      try:
        request = method_container.list_next(request, response)
        if request:
          logging.debug('Iterate over another page of %s', resource_type,
                        extra={'citest_journal':{'nojournal':True}})
      except AttributeError:
        request = None
      more = ' more '

    self.logger.debug('Found total=%d %s', len(all_objects), resource_type)
    return all_objects

  def resource_type_to_discovery_info(self, resource_type):
    """Find the discovery document section for a resource type.

    Args:
      resource_type: [string]  A particular resource type anme defined
          in this agent's discovery document. This could be a subtype
          if the name is in a '<parent>.<sub>' form of arbitrary depth.
    Returns:
       The 'resources' section for the specified resource_type.
    """
    parts = resource_type.split('.')
    node = self.discovery_document
    found = [self.__api_name]

    while parts:
      name = parts.pop(0)
      node = node.get('resources', {}).get(name, None)
      if node is None:
        details = '{path} does not have {name}'.format(
            path='.'.join(found), name=name)
        raise KeyError('Unknown {api} Resource type={type}: {details}'
                       .format(api=self.__api_title, type=resource_type,
                               details=details))
      found.append(name)

    return node

  def resource_type_to_resource_obj(self, resource_type):
    """Get the API on this instance to operate on the given resource_type.

    Args:
      resource_type: [string] The resource type we are looking for as defined
          in the discovery document. This can be a nested type.
    """
    parts = resource_type.split('.')
    name = parts.pop(0)
    resource_obj = vars(self.__service).get(name, None)
    if resource_obj is None:
      raise KeyError('Unknown {api} Resource type={type}'
                     .format(api=self.__api_title, type=name))

    found = [self.__api_name, name]
    while parts:
      name = parts.pop(0)
      resource_obj = vars(resource_obj()).get(name, None)
      if resource_obj is None:
        details = '{path} does not have {name}'.format(
            path='.'.join(found), name=name)
        raise KeyError('Unknown {api} Resource type={type}: {details}'
                       .format(api=self.__api_title, type=resource_type,
                               details=details))
      found.append(name)

    return resource_obj
