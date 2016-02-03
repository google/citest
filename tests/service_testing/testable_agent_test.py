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
import citest.service_testing as st


class FakeAgent(st.TestableAgent):
   def __init__(self):
     super(FakeAgent, self).__init__()


class FakeStatus(st.AgentOperationStatus):
  @property
  def id(self):
    return "test-id"

  @property
  def finished(self):
    return self.__finished

  def __init__(self, operation):
    super(FakeStatus, self).__init__(operation)
    self.__finished = False
    self.calls_remaining = 0
    self.got_refresh_count = 0
    self.got_sleep_count = 0

  def set_expected_iterations(self, n):
    self.__finished = False
    self.calls_remaining = n
    self.got_refresh_count = 0
    self.got_sleep_count = 0

  def _do_sleep(self, secs):
    self.got_sleep_secs = secs
    self.got_sleep_count += 1

  def refresh(self, trace):
    self.got_refresh_count += 1
    if self.calls_remaining >= 0:
      self.calls_remaining -= 1
      if self.calls_remaining < 0:
        self.__finished = True


class TestableAgentTest(unittest.TestCase):
  def test_operation_constructor(self):
    operation = st.AgentOperation('TestStatus')
    self.assertEqual('TestStatus', operation.title)
    self.assertEqual(0, operation.max_wait_secs)

    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    self.assertEqual(agent, operation.agent)

    # Test operation's max_wait_secs is derived from agent value.
    self.assertEqual(-1, operation.max_wait_secs)
    agent.default_max_wait_secs = 10
    self.assertEqual(10, operation.max_wait_secs)

  def test_status_constructor(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)
    self.assertFalse(status.finished)

  def test_operation_bind_agent(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)

    agent2 = FakeAgent()
    self.assertNotEqual(agent, agent2)
    operation.bind_agent(agent2)
    self.assertEqual(agent2, operation.agent)

  def test_no_wait(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    # Operation will finish right away on first refresh() call
    # so we shouldnt be waiting.
    status.set_expected_iterations(0)
    self.assertEqual(0, status.got_refresh_count)
    status.wait()
    self.assertEqual(1, status.got_refresh_count)
    self.assertTrue(status.finished)
    self.assertEqual(0, status.got_sleep_count)

  def test_no_wait_with_max_secs_override(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    # Even though we can wait, we wont because we're finished already.
    status.set_expected_iterations(0)
    status.wait(max_secs=10)
    self.assertEqual(1, status.got_refresh_count)
    self.assertEqual(0, status.got_sleep_count)

  def test_one_wait_cycle(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    # Operation can finish after one wait.
    status.set_expected_iterations(1)
    status.wait()
    self.assertTrue(status.finished)
    self.assertEqual(2, status.got_refresh_count)
    self.assertEqual(1, status.got_sleep_count)
    self.assertEqual(1, status.got_sleep_secs)

  def test_long_wait_cycle(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    # Operation finishes after n waits.
    for i in range(2, 10):
      status.set_expected_iterations(i)
      status.got_sleep_count = 0
      status.got_sleep_secs = 0
      status.wait()
      self.assertEqual(i, status.got_sleep_count)
      self.assertEqual(1, status.got_sleep_secs)

  def test_wait_timeout(self):
    agent = FakeAgent()
    agent.default_max_wait_secs = 5

    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    status.set_expected_iterations(20)
    status.wait()
    self.assertEquals(1 + 5, status.got_refresh_count)
    self.assertEqual(15 - 1, status.calls_remaining)
    self.assertEqual(5, status.got_sleep_count)
    self.assertEqual(1, status.got_sleep_secs)

    # Wait another 5 seconds to show we can continue waiting longer.
    status.got_sleep_count = 0
    status.got_sleep_secs = 0
    status.set_expected_iterations(15)
    status.wait()
    self.assertEqual(10 - 1, status.calls_remaining)
    self.assertEqual(5, status.got_sleep_count)
    self.assertEqual(1, status.got_sleep_secs)

  def test_wait_timeout_with_override(self):
    agent = FakeAgent()
    agent.default_max_wait_secs = 5
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    # Override default wait time.
    # We're telling the status to expect more iterations than
    # it will actually get. All this means is it wont mark
    # the status as being finished.
    status.set_expected_iterations(10)
    status.wait(max_secs=2)
    status.got_sleep_count = 0
    self.assertFalse(status.finished)
    self.assertEqual(8 - 1, status.calls_remaining)

    # Show timeout doesnt prevent us from waiting until completion later.
    status.set_expected_iterations(9)
    status.wait(max_secs=10)
    self.assertEqual(9, status.got_sleep_count)
    self.assertEqual(1, status.got_sleep_secs)
    self.assertEqual(-1, status.calls_remaining)

  def test_wait_interval(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    status.set_expected_iterations(0)
    status.wait(poll_every_secs=60)
    self.assertEqual(0, status.got_sleep_count)

    status.got_sleep_count = 0
    status.set_expected_iterations(2)
    status.wait(poll_every_secs=60)
    self.assertEqual(2, status.got_sleep_count)
    self.assertEqual(60, status.got_sleep_secs)

  def test_wait_interval_truncated(self):
    agent = FakeAgent()
    operation = st.AgentOperation('TestStatus', agent=agent)
    status = FakeStatus(operation)

    status.set_expected_iterations(10)
    status.wait(poll_every_secs=5, max_secs=12)
    self.assertEqual(3, status.got_sleep_count)
    # Last call truncated to the 2 secs remaining.
    self.assertEqual(2, status.got_sleep_secs)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(TestableAgentTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
