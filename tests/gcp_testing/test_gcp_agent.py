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

# pylint: disable=missing-docstring
# pylint: disable=invalid-name

from mock import patch
from citest.gcp_testing import GcpAgent


def _method_spec(parameter_order, optional=None):
  parameters = {key: {'required': True} for key in parameter_order}
  parameters.update({key: {} for key in optional or []})
  return {'parameters': parameters, 'parameterOrder': parameter_order}


class TestGcpAgent(GcpAgent):
  @staticmethod
  @patch('apiclient.discovery.build')
  def make_test_agent(mock_discovery, service=None, default_variables=None):
    doc = TestGcpAgent.generate_discovery_document()
    if service is not None:
      return TestGcpAgent(service, doc, default_variables=default_variables)

    fake_discovery = FakeGcpDiscovery(doc)
    mock_discovery.return_value = fake_discovery
    return TestGcpAgent.make_agent(default_variables)

  @classmethod
  def default_discovery_name_and_version(cls):
    return  'TEST_API', 'TEST_VERSION'

  @staticmethod
  def generate_discovery_document(version='TEST_VERSION'):
    if version != 'TEST_VERSION':
      raise ValueError()

    return {
        'title': 'MockCompute',
        'name': 'mock-compute',
        'resources' : {
            'projects': {
                'methods': {'get': _method_spec(['project'])}},
            'regions': {
                'methods': {'get': _method_spec(['project', 'region']),
                            'list': _method_spec(['project'])}},
            'my_test': {
                'methods': {'get': _method_spec(['r'], ['o']),
                            'list': _method_spec([], ['o'])}}
        }}


class FakeGcpDiscovery(object):
  @property
  def calls(self):
    return self.__calls

  def __init__(self, doc):
    self.__doc = doc
    self.__calls = []

  def apis(self):
    self.__calls.append('apis')
    return self

  def getRest(self, api, version):
    # pylint: disable=unused-argument
    self.__calls.append('getRest')
    return self

  def execute(self):
    self.__calls.append('execute')
    return self.__doc


class FakeGcpService(object):
  @property
  def calls(self):
    return self.__calls

  def __init__(self, execute_response_list):
    self.__calls = []
    self.__execute_response_list = list(execute_response_list)
    self.__execute_response_list.reverse()
    self.my_test = self._my_test  # needs to be a variable
    self.last_list_args = None
    self.last_get_args = None

  def _my_test(self):
    self.__calls.append('my_test')
    return self

  def get(self, **kwargs):
    self.__calls.append('get({0})'.format(kwargs))
    self.last_get_args = dict(**kwargs)
    return self

  def list(self, **kwargs):
    self.__calls.append('list({0})'.format(kwargs))
    self.last_list_args = dict(**kwargs)
    return self

  def execute(self):
    self.__calls.append('execute')
    result = self.__execute_response_list.pop()
    if isinstance(result, Exception):
      raise result
    return result

  def list_next(self, request, response):
    # pylint: disable=unused-argument
    self.__calls.append('list_next')
    return request if self.__execute_response_list else None
