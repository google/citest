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

# pylint: disable=missing-docstring


import unittest

from citest.base import JsonSnapshotHelper
import citest.json_contract as jc
import citest.json_predicate as jp


class TestIoErrorFailureVerifier(jc.ObservationFailureVerifier):
  def _error_comment_or_none(self, error):
    if isinstance(error, IOError):
      return 'HAVE {0}'.format(error.message)
    return None


class ObservationFailureTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)

  def test_observation_failed_error_equal(self):
    self.assertEqual(
        jc.ObservationFailedError([], valid=True),
        jc.ObservationFailedError([], valid=True))
    self.assertEqual(
        jc.ObservationFailedError([ValueError('blah')], valid=True),
        jc.ObservationFailedError([ValueError('blah')], valid=True))
    self.assertNotEqual(
        jc.ObservationFailedError([], valid=True),
        jc.ObservationFailedError([], valid=False))
    self.assertNotEqual(
        jc.ObservationFailedError([ValueError('blah')], valid=True),
        jc.ObservationFailedError([TypeError('blah')], valid=True))

  def __do_test_observation_failure_verifier_with_error(self, klass):
    valid = klass == IOError
    error = klass('Could not connect')
    observation = jc.Observation()
    observation.add_error(error)

    verifier = TestIoErrorFailureVerifier('Test')
    result = verifier(observation)
    self.assertEqual(valid, result.valid)

    if valid:
      attempt = jp.ObjectResultMapAttempt(
          observation, jc.ObservationFailedError([error], valid=valid))
      self.assertFalse(result.bad_results)
      self.assertEqual([attempt], result.good_results)
      self.assertEqual('HAVE Could not connect', result.comment)
    else:
      attempt = jp.ObjectResultMapAttempt(
          observation,
          jp.PredicateResult(
              valid=False, comment='Expected error was not found.'))
      self.assertFalse(result.good_results)
      self.assertEqual([attempt], result.bad_results)
      self.assertEqual('Expected error was not found.', result.comment)

  def test_observation_failure_verifier_with_expected_error(self):
    self.__do_test_observation_failure_verifier_with_error(IOError)

  def test_observation_failure_verifier_with_unexpected_error(self):
    self.__do_test_observation_failure_verifier_with_error(Exception)

  def test_observation_failure_verifier_without_error(self):
    observation = jc.Observation()

    verifier = TestIoErrorFailureVerifier('Test')
    result = verifier(observation)
    self.assertFalse(result.valid)  # Because has no error
    self.assertFalse(result.good_results)
    attempt_list = result.bad_results
    self.assertEqual(
        [jp.ObjectResultMapAttempt(
            observation,
            jp.PredicateResult(
                valid=False,
                comment='Observation had no errors.'))],
        result.bad_results)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(ObservationFailureTest)
  unittest.TextTestRunner(verbosity=2).run(suite)

