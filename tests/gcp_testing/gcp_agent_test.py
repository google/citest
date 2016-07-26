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

import json
import unittest
from mock import patch, Mock
from citest.gcp_testing.gcp_agent import GcpAgent

def method_spec(parameterOrder, optional=None):
    parameters = {key: {'required': True} for key in parameterOrder}
    parameters.update({key: {} for key in optional or []})
    return {'parameters': parameters, 'parameterOrder': parameterOrder}

class TestAgent(GcpAgent):
  @classmethod
  def default_discovery_name_and_version(cls):
    return  'TEST_API', 'TEST_VERSION'

  @staticmethod
  def generate_discovery_document(version='TEST_VERSION'):
    if version != 'TEST_VERSION':
        raise ValueError()
    req = {'required': True}

    return {
        'title': 'MockCompute',
        'name': 'mock-compute',
        'resources' : {
            'projects': {
                'methods': {'get': method_spec(['project'])}},
            'regions': {
                'methods': {'get': method_spec(['project', 'region'])}},
            'my_test': {
                'methods': {'get': method_spec(['r'], ['o']),
                            'list': method_spec([], ['o'])}}
        }}


class FakeDiscovery(object):
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
    self.__calls.append('getRest')
    return self

  def execute(self):
    self.__calls.append('execute')
    return self.__doc


class FakeService(object):
  @property
  def calls(self):
    return self.__calls

  def __init__(self, execute_response_list):
    self.__calls = []
    self.__execute_response_list = list(execute_response_list)
    self.__execute_response_list.reverse()
    self.my_test = self._my_test  # needs to be a variable

  def _my_test(self):
    self.__calls.append('my_test')
    return self

  def get(self, **kwargs):
    self.__calls.append('get({0})'.format(kwargs))
    return self

  def list(self, **kwargs):
    self.__calls.append('list({0})'.format(kwargs))
    return self

  def execute(self):
    self.__calls.append('execute')
    return self.__execute_response_list.pop()

  def list_next(self, request, response):
    self.__calls.append('list_next')
    return request if self.__execute_response_list else None

      
class GcpAgentTest(unittest.TestCase):
  @patch('apiclient.discovery.build')
  def test_download(self, mock_discovery):
    doc = 'HELLO, WORLD!'
    fake_discovery = FakeDiscovery(doc)
    mock_discovery.return_value = fake_discovery
    found = TestAgent.download_discovery_document()
    self.assertEqual(doc, found)
    self.assertEqual(['apis', 'getRest', 'execute'], fake_discovery.calls)

  @patch('apiclient.discovery.build')
  def test_make_agent(self, mock_discovery):
    doc = TestAgent.generate_discovery_document()
    fake_discovery = FakeDiscovery(doc)
    mock_discovery.return_value = fake_discovery
    agent = TestAgent.make_agent()

    self.assertEqual(['apis', 'getRest', 'execute'], fake_discovery.calls)
    self.assertEqual(doc, agent.discovery_document)
    self.assertEqual({}, agent.default_variables)
    
  def test_resource_method_to_variables_no_defaults(self):
    service = None
    discovery_doc = TestAgent.generate_discovery_document()
    agent = TestAgent(service, discovery_doc)

    got = agent.resource_method_to_variables(
        'get', 'my_test', r='R')
    self.assertEqual({'r': 'R'}, got)

    got = agent.resource_method_to_variables(
        'get', 'my_test', r='R', o='O')
    self.assertEqual({'r': 'R', 'o': 'O'}, got)

    got = agent.resource_method_to_variables(
        'get', 'my_test', resource_id='R')
    self.assertEqual({'r': 'R'}, got)

  def test_resource_method_to_variables_with_defaults(self):
    service = None
    discovery_doc = TestAgent.generate_discovery_document()
    agent = TestAgent(service, discovery_doc,
                      default_variables={'r': 'defR', 'o': 'defO'})
    got = agent.resource_method_to_variables(
        'get', 'my_test', r='R', o='O')
    self.assertEqual({'r': 'R', 'o': 'O'}, got)

    got = agent.resource_method_to_variables(
        'get', 'my_test', r='R')
    self.assertEqual({'r': 'R', 'o': 'defO'}, got)

    got = agent.resource_method_to_variables(
        'get', 'my_test', o='O')
    self.assertEqual({'r': 'defR', 'o': 'O'}, got)

    got = agent.resource_method_to_variables(
        'get', 'my_test')
    self.assertEqual({'r': 'defR', 'o': 'defO'}, got)

    got = agent.resource_method_to_variables(
        'get', 'my_test', o=None)
    self.assertEqual({'r': 'defR'}, got)

  def test_invoke(self):
    doc = TestAgent.generate_discovery_document()
    service = FakeService(['HELLO'])
    agent = TestAgent(service, doc)

    got = agent.invoke_resource('get', 'my_test', 'MY_ID')
    args = {'r': 'MY_ID'}
    self.assertEqual(['my_test', 'get({0})'.format(args), 'execute'],
                     service.calls)
    self.assertEqual('HELLO', got)

  def test_list(self):
    doc = TestAgent.generate_discovery_document()
    service = FakeService([{'items': [1, 2, 3]},
                           {'items': [4, 5, 6]}])
    agent = TestAgent(service, doc)

    got = agent.list_resource('my_test')
    self.assertEqual(['my_test', 'list({})', 'execute',
                      'list_next', 'execute', 'list_next'],
                     service.calls)
    self.assertEqual([1, 2, 3, 4, 5, 6], got)


if __name__ == '__main__':
  # pylint: disable=invalid-name
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(GcpAgentTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
