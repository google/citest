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
"""Helper classes for writing unit tests."""

import citest.service_testing as st


class FakeAgent(st.BaseAgent):
  """Fake agents dont do anything other than manage time for wait loops."""

  @property
  def time_series(self):
    return self._time_series

  @time_series.setter
  def time_series(self, time_series):
    self._time_series = time_series

  def next_time(self):
    next_time = self._time_series[0]
    self._time_series = self._time_series[1:]
    return next_time

  def __init__(self, time_series=None):
    super(FakeAgent, self).__init__()
    self._time_series = time_series or [0] * 100


class FakeStatus(st.AgentOperationStatus):
  """Fake status dont do anything other than count calls."""

  @property
  def timed_out(self):
    return self.__timed_out

  @property
  def detail(self):
    return 'Fake Detail'

  @property
  def id(self):
    return 'test-id'

  @property
  def finished(self):
    return self.__finished

  @property
  def finished_ok(self):
    return self.__finished

  def __init__(self, operation):
    super(FakeStatus, self).__init__(operation)
    self.__finished = False
    self.__timed_out = False
    self.calls_remaining = 0
    self.got_refresh_count = 0
    self.got_sleep_count = 0
    self.got_sleep_secs = None

  def set_expected_iterations(self, num):
    self.__finished = False
    self.calls_remaining = num
    self.got_refresh_count = 0
    self.got_sleep_count = 0

  def _now(self):
    return self.operation.agent.next_time()

  def _do_sleep(self, secs):
    self.got_sleep_secs = secs
    self.got_sleep_count += 1

  def refresh(self, trace=True):
    self.got_refresh_count += 1
    if self.calls_remaining >= 0:
      self.calls_remaining -= 1
      if self.calls_remaining < 0:
        self.__finished = True


class FakeOperation(st.AgentOperation):
  """Fake operation doesnt do anything other than return a fake status."""

  def execute(self, agent=None):
    return FakeStatus(self)
