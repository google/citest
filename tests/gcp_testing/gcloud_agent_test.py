# Copyright 2015 Google Inc. All Rights Reserved.
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


import unittest

import fake_gcloud_agent
import citest.gcp_testing as gt


class GCloudAgentTest(unittest.TestCase):
  def setUp(self):
    gt.GCloudAgent.is_preview_type('force-startup')

  def test_gcloud_list(self):
    standard_params = ['--format', 'json', '--project', 'PROJECT']
    gcloud = fake_gcloud_agent.FakeGCloudAgent('PROJECT', 'ZONE')
    gcloud.list_resources('instances')
    self.assertEqual(
      gcloud.last_run_params,
      ['-q', 'compute'] + standard_params + ['instances', 'list'])

    gcloud.list_resources('managed-instance-groups')
    self.assertEqual(
      gcloud.last_run_params,
      ['-q', 'preview'] + standard_params
      + ['managed-instance-groups', '--zone', 'ZONE', 'list'])

    gcloud.describe_resource('instances', 'NAME')
    self.assertEqual(gcloud.last_run_params,
                     ['-q', 'compute'] + standard_params
                     + ['instances', 'describe', 'NAME',  '--zone', 'ZONE'])

    gcloud.describe_resource('managed-instance-groups', 'NAME')
    self.assertEqual(gcloud.last_run_params,
                     ['-q', 'preview'] + standard_params
                     + ['managed-instance-groups', '--zone', 'ZONE',
                        'describe', 'NAME'])


  def test_gcloud_needs_zone(self):
    self.assertFalse(gt.GCloudAgent.command_needs_zone('instances', 'list'))
    self.assertTrue(gt.GCloudAgent.command_needs_zone('instances', 'describe'))
    self.assertTrue(
      gt.GCloudAgent.command_needs_zone('managed-instance-groups', 'list'))
    self.assertTrue(
      gt.GCloudAgent.command_needs_zone('managed-instance-groups', 'describe'))

  def test_build_gcloud_command(self):
    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'instances', ['list', 'X']),
      ['-q', 'compute', '--format', 'json',
       'instances', 'list', 'X'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'instances', ['list', 'X'], zone='ZONE'),
      ['-q', 'compute', '--format', 'json',
       'instances', 'list', 'X', '--zone', 'ZONE'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'instances', ['list', 'X'], zone='ZONE', project='PROJECT'),
      ['-q', 'compute', '--format', 'json', '--project', 'PROJECT',
       'instances', 'list', 'X', '--zone', 'ZONE'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'instances', ['list', 'X'], zone='ZONE', project='PROJECT',
        gcloud_module='MODULE'),
      ['-q', 'MODULE', '--format', 'json', '--project', 'PROJECT',
       'instances', 'list', 'X', '--zone', 'ZONE'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'managed-instance-groups', ['list', 'X']),
      ['-q', 'preview', '--format', 'json',
       'managed-instance-groups', 'list', 'X'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'managed-instance-groups', ['list', 'X'], zone='ZONE'),
      ['-q', 'preview', '--format', 'json',
       'managed-instance-groups', '--zone', 'ZONE', 'list', 'X'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'managed-instance-groups', ['describe', 'X'], zone='ZONE'),
      ['-q', 'preview', '--format', 'json',
       'managed-instance-groups', '--zone', 'ZONE', 'describe', 'X'])


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(GCloudAgentTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
