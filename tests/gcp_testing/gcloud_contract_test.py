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

from citest.base import (
  ExecutionContext,
  JsonSnapshotHelper)

import citest.gcp_testing as gt
import citest.json_contract as jc
import citest.service_testing as st

import fake_gcloud_agent


class GCloudContractTest(unittest.TestCase):

  def test_empty_builder(self):
    context = ExecutionContext()
    default_response = st.CliResponseType(0, '', '')
    gcloud = fake_gcloud_agent.FakeGCloudAgent(
        'PROJECT', 'ZONE', default_response=default_response)
    contract_builder = gt.GCloudContractBuilder(gcloud)
    contract = contract_builder.build()
    results = contract.verify(context)
    self.assertTrue(results)

  def test_list(self):
    # Return a list of two objects -- a dictionary and an array.
    context = ExecutionContext()
    default_response = st.CliResponseType(0, '[{"field":"value"}, [1,2,3]]', '')

    gcloud = fake_gcloud_agent.FakeGCloudAgent(
        'PROJECT', 'ZONE', default_response=default_response)
    contract_builder = gt.GCloudContractBuilder(gcloud)

    c1 = contract_builder.new_clause_builder('TITLE')
    extra_args=['arg1', 'arg2', 'arg3']
    verifier = c1.list_resources('instances', extra_args=extra_args)
    verifier.contains_path_value('field', 'value')

    self.assertTrue(isinstance(verifier, jc.ValueObservationVerifierBuilder))

    # When we build and run the contract, it is going to call the observer.
    # The clause has no constraints so it will succeed. We do this so that
    # we can verify the contract will call the clause which in turn will
    # call the agent with the expected parameters we test for below.
    contract = contract_builder.build()
    self.assertTrue(contract.verify(context))

    command = gcloud.build_gcloud_command_args(
        'instances', ['list'] + extra_args, project='PROJECT')
    self.assertEquals(command, gcloud.last_run_params)

  def test_inspect_not_found_ok(self):
    context = ExecutionContext()

    # Return a 404 Not found
    # The string we return just needs to end with " was not found",
    # which is what gcloud currently returns (subject to change)
    # and all we test for.
    error_response = st.CliResponseType(-
         1, '',
         'ERROR: (gcloud.preview.managed-instance-groups.describe)'
         ' The thing you requested was not found')

    gcloud = fake_gcloud_agent.FakeGCloudAgent(
        'PROJECT', 'ZONE', default_response=error_response)
    contract_builder = gt.GCloudContractBuilder(gcloud)

    context.add_internal('test', 'arg2')
    extra_args = ['arg1', lambda x: x['test'], 'arg3']
    expect_extra_args = ['arg1', 'arg2', 'arg3']

    c1 = contract_builder.new_clause_builder('TITLE')
    verifier = c1.inspect_resource(
        'instances', 'test_name', extra_args=extra_args, no_resource_ok=True)
    verifier.contains_path_value('field', 'value')

    self.assertTrue(isinstance(verifier, jc.ValueObservationVerifierBuilder))

    contract = contract_builder.build()
    verification_result = contract.verify(context)
    self.assertTrue(verification_result,
                    JsonSnapshotHelper.ValueToEncodedJson(verification_result))

    command = gcloud.build_gcloud_command_args(
        'instances', ['describe', 'test_name'] + expect_extra_args,
        project='PROJECT', zone='ZONE')
    self.assertEquals(command, gcloud.last_run_params)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(GCloudContractTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
