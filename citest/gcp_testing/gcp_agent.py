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

import httplib2

from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials

from ..base import JournalLogger
from ..service_testing import BaseAgent


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
  def download_discovery_document(cls, version=None):
    """Return the discovery document for the specified service.

    Args:
      version: [String] The service API version.
    Returns:
      https://developers.google.com/discovery/v1/reference/apis#resource
    """
    api, default_version = cls.default_discovery_name_and_version()
    if version is None:
      version = default_version

    service = discovery.build('discovery', 'v1', http=httplib2.Http())

    # pylint: disable=no-member
    return service.apis().getRest(api=api, version=version).execute()

  @classmethod
  def make_service(cls, version=None, scopes=None, credentials_path=None):
    """Instantiate a client service instance.

    Args:
      version: [string] The version of the API to use.
      scopes: [string] List of scopes to authorize, or None.
      credentials_path: [string] Path to json file with credentials, or None.

    Returns:
      Service
    """
    logger = logging.getLogger(__name__)
    if scopes is None != credentials_path is None:
      raise ValueError(
          'Either provide both scopes and credentials_path or neither')

    api, default_version = cls.default_discovery_name_and_version()
    if version is None:
      version = default_version

    http = httplib2.Http()
    if scopes is not None:
      logger.info('Authenticating %s %s', api, version)
      credentials = ServiceAccountCredentials.from_json_keyfile_name(
          credentials_path, scopes=scopes)
      http = credentials.authorize(http)

    logger.info('Constructing %s service...', api)
    return discovery.build(api, version, http=http)

  @classmethod
  def make_agent(cls, version=None,
                 scopes=None, credentials_path=None,
                 default_variables=None, **kwargs):
    """Factory method to create a new agent instance.

    This is a convienence method to create a new instance with standard
    service and discovery document parameters.

    Args:
      version: [string] The version of the API to use or None for default.
      scopes: [string] List of scopes to authorize, or None.
      credentials_path: [string] Path to json file with credentials, or None.
      default_variables: [dict] Default variable values to pass to methods.
         These are only used when the method has a parameter that was not
         explicitly provided in the invocation.
    Returns:
      Agent
    """
    # pylint: disable=too-many-arguments
    service = cls.make_service(version, scopes, credentials_path)
    discovery_doc = cls.download_discovery_document(version)
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

  def __init__(self, service, discovery_doc, default_variables=None):
    """Constructor.

    Args:
      service: [Service] The service client instance.
      discovery_doc: [dict] The service's Discovery document.
      default_variables: [dict] Default variable values to pass to methods.
         These are only used when the method has a parameter that was not
         explicitly provided in the invocation.
    """
    super(GcpAgent, self).__init__()
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
    discovery_doc = self.discovery_document
    resource_info = discovery_doc.get('resources', {}).get(resource_type, None)
    if resource_info is None:
      raise KeyError('Unknown {0} Resource type={1}'
                     .format(discovery_doc['name'].title(), resource_type))
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

  def get_resource(self, resource_type, resource_id=None, **kwargs):
    """Get instance metadata details.

    Args:
      resource_type: [string] The type of the resource instance to get.
      resource_id: [string] The id of the resource instance to get.
      kwargs: [kwargs] Additional parameters may be required depending
         on the resource type (such as zone, etc).
    """
    return self.invoke_resource(
        'get', resource_type=resource_type, resource_id=resource_id, **kwargs)

  def invoke_resource(self, method, resource_type, resource_id=None, **kwargs):
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
    variables = self.resource_method_to_variables(
        method, resource_type, resource_id=resource_id, **kwargs)

    resource_obj = vars(self.__service).get(resource_type, None)
    if resource_obj is None:
      raise KeyError('Unknown {api} Resource type={type}'
                     .format(api=self.__api_title, type=resource_type))

    JournalLogger.begin_context('Invoke "{method}" {type}'
                                .format(method=method, type=resource_type))
    try:
      JournalLogger.journal_or_log(
          'Requesting {type} {method} {vars}'.format(
              type=resource_type, method=method, vars=variables),
          _module=self.logger.name,
          _context='request')

      request = getattr(resource_obj(), method)(**variables)
      response = request.execute()
      JournalLogger.journal_or_log(
          json.JSONEncoder(
              encoding='utf-8', separators=(',', ': ')).encode(response),
          _module=self.logger.name, _context='response',
          format='json')
    finally:
      JournalLogger.end_context()
      
    return response

  def list_resource(self, resource_type, method_variant='list',
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
    resource_obj = vars(self.__service).get(resource_type, None)
    if resource_obj is None:
      raise KeyError('Unknown {api} Resource type={type}'
                     .format(api=self.__api_title, type=resource_type))

    method_container = resource_obj()
    variables = self.resource_method_to_variables(
        method_variant, resource_type, **kwargs)
    request = getattr(method_container, method_variant)(**variables)

    JournalLogger.begin_context('List {0}'.format(resource_type))
    try:
      all_objects = []
      more = ''
      while request:
        JournalLogger.journal_or_log('Listing {0}{1}'.format(more, resource_type),
                                     _module=self.logger.name,
                                     _context='request')
        response = request.execute()
        JournalLogger.journal_or_log(
            json.JSONEncoder(
                encoding='utf-8', separators=(',', ': ')).encode(response),
            _module=self.logger.name, _context='response',
            format='json')

        response_items = response.get('items', [])
        all_items = (item_list_transform(response_items)
                     if item_list_transform
                     else response_items)
        all_objects.extend(all_items)
        request = method_container.list_next(request, response)
        more = ' more '

      self.logger.info('Found total=%d %s', len(all_objects), resource_type)
    finally:
      JournalLogger.end_context()

    return all_objects
