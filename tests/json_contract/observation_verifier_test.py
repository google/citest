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

from citest.base import Scribe
import citest.json_contract as jc

_called_verifiers = []

def _makeObservationVerifyResult(
      valid, all_results=None,
      good_results=None, bad_results=None, failed_constraints=None):
  all_results = all_results or []
  good_results = good_results or []
  bad_results = bad_results or []
  failed_constraints = failed_constraints or []

  return jc.ObservationVerifyResult(
      valid=valid, observation=jc.Observation(),
      all_results=[], good_results=[], bad_results=[], failed_constraints=[])


class FakeObservationVerifier(jc.ObservationVerifier):
  def __init__(self, title, dnf_verifier, result):
    super(FakeObservationVerifier, self).__init__(
        title=title, dnf_verifiers=dnf_verifier)
    self._result = result

  def __call__(self, observation):
    global _called_verifiers
    _called_verifiers.append(self)
    return self._result


class ObservationVerifierTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      scribe = Scribe()
      msg = 'EXPECT\n{0}\nGOT\n{1}'.format(
        scribe.render_to_string(a),
        scribe.render_to_string(b))
    super(ObservationVerifierTest, self).assertEqual(a, b, msg)

  def test_result_builder_add_good_result(self):
      observation = jc.Observation()
      observation.add_object('A')

      pred = jc.PathPredicate(None, jc.STR_EQ('A'))
      builder = jc.ObservationVerifyResultBuilder(observation)

      map_pred = jc.MapPredicate(pred)
      map_result = map_pred(observation.objects)
      builder.add_map_result(map_result)
      verify_results = builder.build(True)

      self.assertTrue(verify_results)
      self.assertEqual(observation, verify_results.observation)
      self.assertEqual([], verify_results.bad_results)
      self.assertEqual([], verify_results.failed_constraints)
      self.assertEqual(map_result.results, verify_results.all_results)
      self.assertEqual(map_result.good_object_result_mappings,
                       verify_results.good_results)


  def test_result_builder_add_bad_result(self):
      observation = jc.Observation()
      observation.add_object('A')

      pred = jc.PathPredicate(None, jc.STR_EQ('B'))
      builder = jc.ObservationVerifyResultBuilder(observation)

      map_pred = jc.MapPredicate(pred)
      map_result = map_pred(observation.objects)
      builder.add_map_result(map_result)
      verify_results = builder.build(False)

      self.assertFalse(verify_results)
      self.assertEqual(observation, verify_results.observation)
      self.assertEqual([], verify_results.good_results)
      self.assertEqual([pred], verify_results.failed_constraints)
      self.assertEqual(map_result.results, verify_results.all_results)
      self.assertEqual(map_result.bad_object_result_mappings,
                       verify_results.bad_results)

  def test_result_builder_add_mixed_results(self):
      observation = jc.Observation()
      observation.add_object('GOOD')
      observation.add_object('BAD')

      pred = jc.PathPredicate(None, jc.STR_EQ('GOOD'))
      builder = jc.ObservationVerifyResultBuilder(observation)

      map_pred = jc.MapPredicate(pred)
      map_result = map_pred(observation.objects)
      builder.add_map_result(map_result)
      verify_results = builder.build(False)

      self.assertFalse(verify_results)
      self.assertEqual(observation, verify_results.observation)
      self.assertEqual(map_result.good_object_result_mappings,
                       verify_results.good_results)
      self.assertEqual([], verify_results.failed_constraints)
      self.assertEqual(map_result.results, verify_results.all_results)
      self.assertEqual(map_result.bad_object_result_mappings,
                       verify_results.bad_results)

  def test_result_observation_verifier_conjunction_ok(self):
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    for i in range(3):
      result = _makeObservationVerifyResult(valid=True)
      verifier = FakeObservationVerifier(
         title=i, dnf_verifier=[], result=result)
      verifiers.append(verifier)
      results.append(result)
      builder.append_verifier(verifier)

    # verify build can work multiple times
    self.assertEqual(builder.build(), builder.build())
    verifier = builder.build()
    self.assertEqual([verifiers], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(
        True, all_results=results, good_results=results)

    global _called_verifiers
    _called_verifiers = []
    got = verifier(jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers, _called_verifiers)

  def test_result_observation_verifier_conjunction_failure_aborts_early(self):
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    for i in range(3):
      result = _makeObservationVerifyResult(valid=False)
      verifier = FakeObservationVerifier(
         title=i, dnf_verifier=[], result=result)
      verifiers.append(verifier)
      results.append(result)
      builder.append_verifier(verifier)

    # verify build can work multiple times
    self.assertEqual(builder.build(), builder.build())
    verifier = builder.build()
    self.assertEqual([verifiers], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(
        False, all_results=[results[0]], bad_results=[results[0]])

    global _called_verifiers
    _called_verifiers = []
    got = verifier(jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers[:1], _called_verifiers)

  def test_result_observation_verifier_disjunction_success_aborts_early(self):
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    for i in range(2):
      result = _makeObservationVerifyResult(valid=True)
      verifier = FakeObservationVerifier(
         title=i, dnf_verifier=[], result=result)
      verifiers.append(verifier)
      results.append(result)
      builder.append_verifier(verifier, new_term=True)

    verifier = builder.build()
    self.assertEqual([verifiers[0:1], verifiers[1:2]], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(
        True, all_results=[results[0]], bad_results=[results[0]])

    global _called_verifiers
    _called_verifiers = []
    got = verifier(jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers[:1], _called_verifiers)

  def test_result_observation_verifier_disjunction_failure(self):
    builder = jc.ObservationVerifierBuilder(title='Test')
    verifiers = []
    results = []
    for i in range(2):
      result = _makeObservationVerifyResult(valid=False)
      verifier = FakeObservationVerifier(
         title=i, dnf_verifier=[], result=result)
      verifiers.append(verifier)
      results.append(result)
      builder.append_verifier(verifier, new_term=True)

    verifier = builder.build()
    self.assertEqual([verifiers[0:1], verifiers[1:2]], verifier.dnf_verifiers)

    expect = _makeObservationVerifyResult(
        False, all_results=[results], bad_results=[results])

    global _called_verifiers
    _called_verifiers = []
    got = verifier(jc.Observation())

    self.assertEqual(expect, got)
    self.assertEqual(verifiers, _called_verifiers)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(ObservationVerifierTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
