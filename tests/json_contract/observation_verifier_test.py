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
# pylint: disable=invalid-name


import unittest

from citest.base import (
  ExecutionContext,
  JsonSnapshotHelper)

import citest.json_contract as jc
import citest.json_predicate as jp


_called_verifiers = []
_TEST_FOUND_ERROR_COMMENT='Found error.'


class TestObsoleteObservationFailureVerifier(jc.ObservationFailureVerifier):
  def __init__(self, title, expect):
    super(TestObsoleteObservationFailureVerifier, self).__init__(title)
    self.__expect = expect

  def _error_comment_or_none(self, error):
    if error.message == self.__expect:
      return _TEST_FOUND_ERROR_COMMENT
    return None


def _makeObservationVerifyResult(
    valid, observation=None,
    good_results=None, bad_results=None, failed_constraints=None):
  default_result = jp.PredicateResult(valid=valid)
  good_results = good_results or ([default_result] if valid else [])
  bad_results = bad_results or ([] if valid else [default_result])
  failed_constraints = failed_constraints or []

  observation = observation or jc.Observation()
  good_attempt_results = [jp.ObjectResultMapAttempt(observation, result)
                          for result in good_results]
  bad_attempt_results = [jp.ObjectResultMapAttempt(observation, result)
                         for result in bad_results]
  return jc.ObservationVerifyResult(
      valid=valid, observation=observation,
      good_results=good_attempt_results,
      bad_results=bad_attempt_results,
      failed_constraints=failed_constraints)


class FakeObservationVerifier(jc.ObservationVerifier):
  def __init__(self, title, dnf_verifier, result):
    super(FakeObservationVerifier, self).__init__(
        title=title, dnf_verifiers=dnf_verifier)
    self.__result = result

  def __call__(self, context, observation):
    _called_verifiers.append(self)
    return self.__result


class ObservationVerifierTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0!r}\nGOT\n{1!r}'.format(expect, have)

    JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)

  def test_result_builder_add_good_result(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')

    pred = jp.PathPredicate(None, jp.STR_EQ('A'))
    builder = jc.ObservationVerifyResultBuilder(observation)

    map_pred = jp.MapPredicate(pred)
    map_result = map_pred(context, observation.objects)
    builder.add_map_result(map_result)
    verify_results = builder.build(True)

    self.assertTrue(verify_results)
    self.assertEqual(observation, verify_results.observation)
    self.assertEqual([], verify_results.bad_results)
    self.assertEqual([], verify_results.failed_constraints)
    self.assertEqual(map_result.good_object_result_mappings,
                     verify_results.good_results)


  def test_result_builder_add_bad_result(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('A')

    pred = jp.PathPredicate(None, jp.STR_EQ('B'))
    builder = jc.ObservationVerifyResultBuilder(observation)

    map_pred = jp.MapPredicate(pred)
    map_result = map_pred(context, observation.objects)
    builder.add_map_result(map_result)
    verify_results = builder.build(False)

    self.assertFalse(verify_results)
    self.assertEqual(observation, verify_results.observation)
    self.assertEqual([], verify_results.good_results)
    self.assertEqual([pred], verify_results.failed_constraints)
    self.assertEqual(map_result.bad_object_result_mappings,
                     verify_results.bad_results)

  def test_result_builder_add_mixed_results(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_object('GOOD')
    observation.add_object('BAD')

    pred = jp.PathPredicate(None, jp.STR_EQ('GOOD'))
    builder = jc.ObservationVerifyResultBuilder(observation)

    map_pred = jp.MapPredicate(pred)
    map_result = map_pred(context, observation.objects)
    builder.add_map_result(map_result)
    verify_results = builder.build(False)

    self.assertFalse(verify_results)
    self.assertEqual(observation, verify_results.observation)
    self.assertEqual(map_result.good_object_result_mappings,
                     verify_results.good_results)
    self.assertEqual([], verify_results.failed_constraints)
    self.assertEqual(map_result.bad_object_result_mappings,
                     verify_results.bad_results)

  def test_result_observation_verifier_conjunction_ok(self):
    context = ExecutionContext()
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    pred_results = []
    for i in range(3):
      this_result = jp.PredicateResult(True, comment='Pred {0}'.format(i))
      pred_results.append(this_result)
      result = _makeObservationVerifyResult(
          valid=True, good_results=[this_result])
      fake_verifier = FakeObservationVerifier(
          title=i, dnf_verifier=[], result=result)
      verifiers.append(fake_verifier)
      builder.AND(fake_verifier)

    # verify build can work multiple times
    self.assertEqual(builder.build(), builder.build())
    verifier = builder.build()
    self.assertEqual([verifiers], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(True, good_results=pred_results)

    global _called_verifiers
    _called_verifiers = []
    got = verifier(context, jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers, _called_verifiers)

  def test_result_observation_verifier_conjunction_failure_aborts_early(self):
    context = ExecutionContext()
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    pred_results = [jp.PredicateResult(False, comment='Result %d' % i)
                                       for i in range(3)]
    for i in range(3):
      result = _makeObservationVerifyResult(
          valid=False, bad_results=[pred_results[i]])
      fake_verifier = FakeObservationVerifier(
          title=i, dnf_verifier=[], result=result)
      verifiers.append(fake_verifier)
      results.append(result)
      builder.AND(fake_verifier)

    # verify build can work multiple times
    self.assertEqual(builder.build(), builder.build())
    verifier = builder.build()
    self.assertEqual([verifiers], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(
        False, bad_results=[pred_results[0]])

    global _called_verifiers
    _called_verifiers = []
    got = verifier(context, jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers[:1], _called_verifiers)

  def test_result_observation_verifier_disjunction_success_aborts_early(self):
    context = ExecutionContext()
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    pred_results = [jp.PredicateResult(False, comment='Result %d' % i)
                                       for i in range(2)]
    for i in range(2):
      result = _makeObservationVerifyResult(
          valid=True, good_results=[pred_results[i]])
      fake_verifier = FakeObservationVerifier(
          title=i, dnf_verifier=[], result=result)
      verifiers.append(fake_verifier)
      results.append(result)
      builder.OR(fake_verifier)

    verifier = builder.build()
    self.assertEqual([verifiers[0:1], verifiers[1:2]], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(True, good_results=[pred_results[0]])

    global _called_verifiers
    _called_verifiers = []
    got = verifier(context, jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers[:1], _called_verifiers)

  def test_result_observation_verifier_disjunction_failure(self):
    context = ExecutionContext()
    observation = jc.Observation()
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    pred_results = [jp.PredicateResult(False, comment='Result %d' % i)
                                       for i in range(2)]
    for i in range(2):
      result = _makeObservationVerifyResult(observation=observation,
          valid=False, bad_results=[pred_results[i]])
      fake_verifier = FakeObservationVerifier(
          title=i, dnf_verifier=[], result=result)
      verifiers.append(fake_verifier)
      results.append(result)
      builder.OR(fake_verifier)

    verifier = builder.build()
    self.assertEqual([verifiers[0:1], verifiers[1:2]], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(
        False, observation=observation, bad_results=pred_results)

    global _called_verifiers
    _called_verifiers = []
    got = verifier(context, observation)

    self.assertEqual(expect, got)
    self.assertEqual(verifiers, _called_verifiers)

  def test_obsolete_observation_failure_ok(self):
    error_text = 'the error'
    context = ExecutionContext()

    observation = jc.Observation()
    error = ValueError(error_text)
    observation.add_error(error)

    failure_verifier = TestObsoleteObservationFailureVerifier(
        'Test', error_text)
    failure_pred_result = jc.ObservationFailedError([error], valid=True)

    expect_failure = jc.ObservationVerifyResult(
        valid=True, observation=observation,
        good_results=[jp.ObjectResultMapAttempt(observation,
                                                failure_pred_result)],
        bad_results=[], failed_constraints=[],
        comment=_TEST_FOUND_ERROR_COMMENT)
    got = failure_verifier(context, observation)
    self.assertEqual(expect_failure, got)

    builder = jc.ObservationVerifierBuilder(title='Test')
    builder.EXPECT(failure_verifier)
    verifier = builder.build()

    expect = jc.ObservationVerifyResult(
        valid=True, observation=observation,
        good_results=expect_failure.good_results,
        bad_results=[], failed_constraints=[])

    got = verifier(context, observation)
    self.assertEqual(expect, got)

  def test_observation_failure_ok(self):
    error_text = 'the error'
    context = ExecutionContext()

    observation = jc.Observation()
    error = ValueError(error_text)
    observation.add_error(error)

    exception_pred = jp.ExceptionMatchesPredicate(
        ValueError, regex=error_text)
    builder = jc.ObservationVerifierBuilder(title='Test')
    builder.EXPECT(jc.ObservationErrorPredicate(jp.LIST_MATCHES([exception_pred])))
    failure_verifier = builder.build()

    observation_predicate_result = jc.ObservationPredicateResult(
        True, observation, jp.LIST_MATCHES([exception_pred]),
        jp.LIST_MATCHES([exception_pred])(context, [error]))

    expect_failure = jc.ObservationVerifyResult(
        True, observation,
        good_results=[observation_predicate_result],
        bad_results=[], failed_constraints=[])
    got = failure_verifier(context, observation)
    self.assertEqual(expect_failure, got)

  def test_obsolete_observation_failure_not_ok(self):
    error_text = 'the error'
    context = ExecutionContext()
    observation = jc.Observation()
    error = ValueError('not the error')
    observation.add_error(error)

    failure_verifier = TestObsoleteObservationFailureVerifier(
        'Test', error_text)
    comment = failure_verifier._error_not_found_comment(observation)
    failure_pred_result = jp.PredicateResult(valid=False, comment=comment)

    expect_failure = jc.ObservationVerifyResult(
        valid=False, observation=observation,
        bad_results=[jp.ObjectResultMapAttempt(observation,
                                               failure_pred_result)],
        good_results=[], failed_constraints=[],
        comment=comment)
    self.assertEqual(expect_failure, failure_verifier(context, observation))

    builder = jc.ObservationVerifierBuilder(title='Test Verifier')
    builder.EXPECT(failure_verifier)
    verifier = builder.build()

    expect = jc.ObservationVerifyResult(
        valid=False, observation=observation,
        bad_results=expect_failure.bad_results,
        good_results=[], failed_constraints=[])
    got = verifier(context, observation)
    self.assertEqual(expect, got)

  def test_obsolete_observation_failure_or_found(self):
    context = ExecutionContext()
    observation = jc.Observation()
    observation.add_error(ValueError('not the error'))

    failure_verifier = TestObsoleteObservationFailureVerifier(
        'Verify', 'NotFound')
    comment = failure_verifier._error_not_found_comment(observation)
    failure_result = jp.PredicateResult(valid=False, comment=comment)
    # We've already established this result is what we expect
    bad_observation_result = failure_verifier(context, observation)

    success_pred_result = jp.PredicateResult(valid=True)
    good_observation_result = _makeObservationVerifyResult(
      valid=True,
      good_results=[success_pred_result],
      observation=observation)
    success_verifier = FakeObservationVerifier(
          'Found', dnf_verifier=[], result=good_observation_result)

    builder = jc.ObservationVerifierBuilder(title='Observation Verifier')
    builder.EXPECT(failure_verifier).OR(success_verifier)
    verifier = builder.build()

    expect = jc.ObservationVerifyResult(
        valid=True, observation=observation,
        bad_results=bad_observation_result.bad_results,
        good_results=good_observation_result.good_results,
        failed_constraints=[])

    got = verifier(context, observation)
    self.assertEqual(expect, got)


if __name__ == '__main__':
  unittest.main()

