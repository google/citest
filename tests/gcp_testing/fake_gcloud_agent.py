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


import citest.gcp_testing as gcp_testing
import citest.service_testing as st


class FakeGCloudAgent(gcp_testing.GCloudAgent):

  def __init__(self, project, zone, default_response=None):
    """Construct new agent instance.

    Args:
      project: The value for the agent's project attribute (could be bogus).
      zone: The value for the agent's zone attribute (could be bogus).
      default_response: If provided, the default CliResponseType that the agent
          will return.
    """
    super(FakeGCloudAgent, self).__init__(project, zone)
    self._default_response = default_response
    self.last_run_params = []

  @staticmethod
  def new(default_response):
    return FakeGCloudAgent('FAKE_PROJECT', 'FAKE_ZONE', response)

  def run(self, params, trace=True):
    self.last_run_params = list(params)
    return self._default_response
