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

from citest.base.scribe import Scribe
import citest.gcp_testing as gt
import citest.json_contract as jc
import citest.service_testing as st

import fake_gcloud_agent


class GceContractTest(unittest.TestCase):

  def test_empty_builder(self):
    default_response = st.CliResponseType(0, '', '')
    gcloud = fake_gcloud_agent.FakeGCloudAgent(
        'PROJECT', 'ZONE', default_response)
    contract_builder = gt.GceContractBuilder(gcloud)
    contract = contract_builder.build()
    results = contract.verify()
    self.assertTrue(results)

  def test_list(self):
    # Return a list of two objects -- a dictionary and an array.
    default_response = st.CliResponseType(0, '[{"field":"value"}, [1,2,3]]', '')

    gcloud = fake_gcloud_agent.FakeGCloudAgent(
        'PROJECT', 'ZONE', default_response)
    contract_builder = gt.GceContractBuilder(gcloud)

    c1 = contract_builder.new_clause_builder('TITLE')
    extra_args=['arg1', 'arg2', 'arg3']
    verifier = c1.list_resources('instances', extra_args=extra_args)
    verifier.contains('field', 'value')

    self.assertTrue(isinstance(verifier, jc.ValueObservationVerifierBuilder))

    # When we build and run the contract, it is going to call the observer.
    # The clause has no constraints so it will succeed. We do this so that
    # we can verify the contract will call the clause which in turn will
    # call the agent with the expected parameters we test for below.
    contract = contract_builder.build()
    self.assertTrue(contract.verify())

    command = gcloud.build_gcloud_command_args(
        'instances', ['list'] + extra_args, project='PROJECT')
    self.assertEquals(command, gcloud.last_run_params)

  def test_inspect_not_found_ok(self):
    # Return a 404 Not found
    error_response = st.CliResponseType(-
         1, '',
         'ERROR: (gcloud.preview.managed-instance-groups.describe)'
         ' ResponseError: code=404, message=Not Found')

    gcloud = fake_gcloud_agent.FakeGCloudAgent(
        'PROJECT', 'ZONE', error_response)
    contract_builder = gt.GceContractBuilder(gcloud)

    extra_args=['arg1', 'arg2', 'arg3']

    c1 = contract_builder.new_clause_builder('TITLE')
    verifier = c1.inspect_resource(
        'instances', 'test_name', extra_args=extra_args, no_resource_ok=True)
    verifier.contains('field', 'value')

    self.assertTrue(isinstance(verifier, jc.ValueObservationVerifierBuilder))

    contract = contract_builder.build()
    verification_result = contract.verify()
    self.assertTrue(verification_result, Scribe().render(verification_result))

    command = gcloud.build_gcloud_command_args(
        'instances', ['describe', 'test_name'] + extra_args,
        project='PROJECT', zone='ZONE')
    self.assertEquals(command, gcloud.last_run_params)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(GceContractTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
