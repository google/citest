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
      ['-q', 'compute'] + standard_params
      + ['instance-groups', 'managed', 'list', '--zone', 'ZONE'])

    gcloud.list_resources('unmanaged-instance-groups')
    self.assertEqual(
      gcloud.last_run_params,
      ['-q', 'compute'] + standard_params
      + ['instance-groups', 'unmanaged', 'list', '--zone', 'ZONE'])

    gcloud.describe_resource('instances', 'NAME')
    self.assertEqual(gcloud.last_run_params,
                     ['-q', 'compute'] + standard_params
                     + ['instances', 'describe', 'NAME',  '--zone', 'ZONE'])

    gcloud.describe_resource('managed-instance-groups', 'NAME')
    self.assertEqual(gcloud.last_run_params,
                     ['-q', 'compute'] + standard_params
                     + ['instance-groups', 'managed',
                        'describe', 'NAME', '--zone', 'ZONE'])

    gcloud.describe_resource('unmanaged-instance-groups', 'NAME')
    self.assertEqual(gcloud.last_run_params,
                     ['-q', 'compute'] + standard_params
                     + ['instance-groups', 'unmanaged',
                        'describe', 'NAME', '--zone', 'ZONE'])


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
      ['-q', 'compute', '--format', 'json',
       'instance-groups', 'managed', 'list', 'X'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'managed-instance-groups', ['list', 'X']),
      ['-q', 'compute', '--format', 'json',
       'instance-groups', 'managed', 'list', 'X'])

    self.assertEqual(
      gt.GCloudAgent.build_gcloud_command_args(
        'managed-instance-groups', ['describe', 'X'], zone='XYZ'),
      ['-q', 'compute', '--format', 'json',
       'instance-groups', 'managed', 'describe', 'X', '--zone', 'XYZ'])

  def test_run_without_account(self):
    gcloud = fake_gcloud_agent.FakeGCloudAgent('PROJECT', 'ZONE')
    self.assertEqual(['gcloud', 'a', 'b', 1],
                     gcloud._args_to_full_commandline(['a', 'b', 1]))

  def test_run_with_account(self):
    gcloud = fake_gcloud_agent.FakeGCloudAgent('PROJECT', 'ZONE',
                                               service_account='ACCOUNT')
    self.assertEqual(['gcloud', '--account', 'ACCOUNT', 'a', 'b', 1],
                     gcloud._args_to_full_commandline(['a', 'b', 1]))
    

if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(GCloudAgentTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
