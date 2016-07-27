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
from mock import Mock

from citest.base import JsonSnapshotHelper

from citest.json_predicate import (
    CompositePredicateResultBuilder,
    FieldDifference,
    NUM_GE,
    PathPredicate,
    PathValue,
    PathValueResult)

from citest.gcp_testing import (
    GcpAgent,
    QuotaPredicate,
    make_quota_contract)


REQ = {'required': True}
MOCK_DISCOVERY = {
  'title': 'MockCompute',
  'name': 'mock-compute',
  'resources' : {
      'projects': {
          'methods': {'get': {'parameters': {'project': REQ},
                              'parameterOrder': ['project']}}},
      'regions': {
          'methods': {'get': {'parameters': {'project': REQ, 'region': REQ},
                              'parameterOrder': ['project', 'region']}}}
      }}


def make_quota_result(valid, source, require, metric):
  """Construct the values returned by QuotaPredicate.

  These are what is currently implemented, but the current implementation
  is not correct because it uses PathValue of made up paths rather than
  expressing that we are looking for the difference among two paths.
  """
  diff = FieldDifference('limit', 'usage')
  for value in source:
    if value['metric'] == metric:
      return PathPredicate('', pred=NUM_GE(require[metric]), transform=diff)(value)

  raise ValueError('Missing metric')


class GcpQuotaPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    try:
      JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)
    except AssertionError:
      print '\nEXPECT\n{0!r}\n\nGOT\n{1!r}\n'.format(expect, have)
      raise

  def test_good(self):
    source = [{'metric': 'A', 'limit': 100.0, 'usage': 0.0},
              {'metric': 'B', 'limit': 100.0, 'usage': 90.0},
              {'metric': 'C', 'limit': 100.0, 'usage': 100.0}]
    require = {'A': 95.0, 'B': 10.0}
    pred = QuotaPredicate(require)
    builder = CompositePredicateResultBuilder(pred)
    builder.append_result(make_quota_result(True, source, require, 'A'))
    builder.append_result(make_quota_result(True, source, require, 'B'))
    builder.comment = 'Satisfied all 2 metrics.'

    result = pred(source)
    self.assertTrue(result)
    self.assertEqual(result, builder.build(True))

  def test_bad(self):
    source = [{'metric': 'A', 'limit': 100.0, 'usage': 0.0},
              {'metric': 'B', 'limit': 100.0, 'usage': 90.0},
              {'metric': 'C', 'limit': 100.0, 'usage': 100.0}]
    require = {'A': 95.0, 'B': 15.0}
    pred = QuotaPredicate(require)
    builder = CompositePredicateResultBuilder(pred)
    builder.append_result(make_quota_result(True, source, require, 'A'))
    builder.append_result(make_quota_result(False, source, require, 'B'))
    builder.comment = 'Insufficient C.'

    result = pred(source)
    self.assertFalse(result)

  def make_mock_service(self, project_quota, region_quota):
    mock_project_method = Mock()
    mock_project_method.execute = Mock(return_value={'quotas': project_quota})
    mock_projects = Mock()
    mock_projects.get = Mock(return_value=mock_project_method)

    mock_region_method = Mock()
    mock_region_method.execute = Mock(return_value={'quotas': region_quota})
    mock_regions = Mock()
    mock_regions.get = Mock(return_value=mock_region_method)

    mock_service = Mock()
    mock_service.projects = Mock(return_value=mock_projects)
    mock_service.regions = Mock(return_value=mock_regions)
    return mock_service

  def test_contract_ok(self):
    source = [{'metric': 'A', 'limit': 100.0, 'usage': 0.0},
              {'metric': 'B', 'limit': 100.0, 'usage': 90.0},
              {'metric': 'C', 'limit': 100.0, 'usage': 100.0}]

    mock_service = self.make_mock_service(source, source)
    observer = GcpAgent(service=mock_service, discovery_doc=MOCK_DISCOVERY,
                        default_variables={'project': 'PROJECT'})
    project_quota = {'A': 95.0, 'B': 10.0}
    regions = [('region1', project_quota)]

    contract = make_quota_contract(observer, project_quota, regions)
    got_result = contract.verify()
    self.assertTrue(got_result)
    self.assertEqual(2, len(got_result.clause_results))

  def test_contract_bad(self):
    source = [{'metric': 'A', 'limit': 100.0, 'usage': 0.0},
              {'metric': 'B', 'limit': 100.0, 'usage': 90.0},
              {'metric': 'C', 'limit': 100.0, 'usage': 100.0}]
    mock_service = self.make_mock_service(source, source)
    observer = GcpAgent(service=mock_service, discovery_doc=MOCK_DISCOVERY,
                        default_variables={'project': 'PROJECT'})

    project_quota = {'A': 95.0, 'B': 10.0}
    regions = [('region1', project_quota), ('region2', {'C': 1.0})]

    contract = make_quota_contract(observer, project_quota, regions)
    result = contract.verify()
    self.assertFalse(result)
    self.assertEqual(3, len(result.clause_results))
    self.assertTrue(result.clause_results[0])
    self.assertTrue(result.clause_results[1])
    self.assertFalse(result.clause_results[2])


if __name__ == '__main__':
  # pylint: disable=invalid-name
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(GcpQuotaPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
