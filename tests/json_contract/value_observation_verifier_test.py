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


_LETTER_DICT = { 'a':'A', 'b':'B', 'z':'Z' }
_NUMBER_DICT = { 'a':1, 'b':2, 'three':3 }

_COMPOSITE_DICT = { 'letters': _LETTER_DICT, 'numbers': _NUMBER_DICT }

_LETTER_ARRAY = ['a', 'b', 'c']
_NUMBER_ARRAY = [1, 2, 3]
_DICT_ARRAY = [{}, _LETTER_DICT, _NUMBER_DICT, _COMPOSITE_DICT]
_MULTI_ARRAY = [ _LETTER_DICT, _NUMBER_DICT, _LETTER_DICT, _NUMBER_DICT]


class JsonValueObservationVerifierTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECT\n{0}\nGOT\n{1}'.format(
        Scribe().render(a),
        Scribe().render(b))
    super(JsonValueObservationVerifierTest, self).assertEqual(a, b, msg)

  def test_verifier_builder_add_constraint(self):
      aA = jc.PathPredicate('a', jc.STR_EQ('A'))
      bB = jc.PathPredicate('b', jc.STR_EQ('B'))
      builder = jc.ValueObservationVerifierBuilder('TestAddConstraint')
      builder.add_constraint(aA)
      builder.add_constraint(bB)
      verifier = builder.build()
      self.assertEqual('TestAddConstraint', verifier.title)
      self.assertEqual([aA, bB], verifier.constraints)

  def test_verifier_builder_contains_group(self):
      aA = jc.PathPredicate('a', jc.STR_EQ('A'))
      bB = jc.PathPredicate('b', jc.STR_EQ('B'))
      builder = jc.ValueObservationVerifierBuilder('TestContainsGroup')
      builder.contains_pred('a', jc.STR_EQ('A'))
      builder.contains_pred('b', jc.STR_EQ('B'))
      verifier = builder.build()

      count_aA = jc.CardinalityPredicate(aA, 1, None)
      count_bB = jc.CardinalityPredicate(bB, 1, None)
      self.assertEqual([count_aA, count_bB], verifier.constraints)

  def test_object_observation_verifier_multiple_constraint_found(self):
    pred_list = [jc.PathPredicate('a', jc.STR_EQ('A')),
                 jc.PathPredicate('b', jc.STR_EQ('B'))]
    # This is our object verifier for these tests.
    verifier = jc.ValueObservationVerifier(
        title='Find Both', constraints=pred_list)

    test_cases = [('dict', _LETTER_DICT),
                  ('array', _DICT_ARRAY),
                  ('multi', _MULTI_ARRAY)]
    for test in test_cases:
      observation = jc.Observation()
      builder = jc.ObservationVerifyResultBuilder(observation)

      obj = test[1]
      if isinstance(test, list):
        observation.add_all_objects(obj)
      else:
        observation.add_object(obj)

      for pred in pred_list:
        builder.add_map_result(jc.MapPredicate(pred)(observation.objects))

      verify_results = builder.build(True)

      try:
        self._try_verify(verifier, observation, True, verify_results)
      except:
        print 'testing ' + test[0]
        raise

  def test_object_observation_verifier_one_constraint_not_found(self):
    pred_list = [jc.PathPredicate('a', jc.STR_EQ('NOT_FOUND'))]

    # This is our object verifier for these tests.
    verifier = jc.ValueObservationVerifier(
        title='Cannot find one', constraints=pred_list)

    test_cases = [('array', _DICT_ARRAY),
                  ('dict', _LETTER_DICT),
                  ('array', _DICT_ARRAY),
                  ('multi', _MULTI_ARRAY)]

    for test in test_cases:
      observation = jc.Observation()
      builder = jc.ObservationVerifyResultBuilder(observation)

      obj = test[1]
      if isinstance(test, list):
        observation.add_all_objects(obj)
      else:
        observation.add_object(obj)

      for pred in pred_list:
        builder.add_map_result(jc.MapPredicate(pred)(observation.objects))

      verify_results = builder.build(False)

      try:
        self._try_verify(verifier, observation, False, verify_results)
      except:
        print 'testing ' + test[0]
        raise

  def test_object_observation_verifier_multiple_constraint_not_found(self):
    pred_list = [jc.PathPredicate('a', jc.STR_EQ('NOT_FOUND')),
                 jc.PathPredicate('b', jc.STR_EQ('NOT_FOUND'))]

    # This is our object verifier for these tests.
    verifier = jc.ValueObservationVerifier(
        title='Cannot find either', constraints=pred_list)

    test_cases = [('array', _DICT_ARRAY),
                  ('dict', _LETTER_DICT),
                  ('array', _DICT_ARRAY),
                  ('multi', _MULTI_ARRAY)]

    for test in test_cases:
      observation = jc.Observation()
      builder = jc.ObservationVerifyResultBuilder(observation)

      obj = test[1]
      if isinstance(test, list):
        observation.add_all_objects(obj)
      else:
        observation.add_object(obj)

      for pred in pred_list:
        builder.add_map_result(jc.MapPredicate(pred)(observation.objects))

      verify_results = builder.build(False)

      try:
        self._try_verify(verifier, observation, False, verify_results)
      except:
        print 'testing ' + test[0]
        raise

  def test_object_observation_verifier_some_but_not_all_constraints_found(self):
    pred_list = [jc.PathPredicate('a', jc.STR_EQ('NOT_FOUND')),
                 jc.PathPredicate('b', jc.STR_EQ('B'))]

    # This is our object verifier for these tests.
    verifier = jc.ValueObservationVerifier(
        title='Find one of two', constraints=pred_list)

    test_cases = [('array', _DICT_ARRAY),
                  ('dict', _LETTER_DICT),
                  ('array', _DICT_ARRAY),
                  ('multi', _MULTI_ARRAY)]

    for test in test_cases:
      observation = jc.Observation()
      builder = jc.ObservationVerifyResultBuilder(observation)

      obj = test[1]
      if isinstance(test, list):
        observation.add_all_objects(obj)
      else:
        observation.add_object(obj)

      for pred in pred_list:
        builder.add_map_result(jc.MapPredicate(pred)(observation.objects))

      verify_results = builder.build(False)

      try:
        self._try_verify(verifier, observation, False, verify_results)
      except:
        print 'testing ' + test[0]
        raise

  def _try_verify(self, verifier, observation, expect_ok, expect_results=None,
                  dump=False):
    """Helper function for a verifier result on a given observation.

    Args:
      verifier: The jc.ObservationVerifier to run.
      observation: The jc.Observation to run on.
      expect_ok: Whether we expect the verifier to succeed or not.
      expect_results: If not None, then the expected verify_results.
      dump: If True then print the verify_results to facilitate debugging.
    """
    verify_results = verifier(observation)

    # Assert that the observation was unchanged.
    self.assertEqual(verify_results.observation, observation)

    ok = verify_results.__nonzero__()
    scribe = Scribe()
    error_msg = '{expect_ok}!={ok}\n{errors}'.format(
        expect_ok=expect_ok, ok=ok,
        errors=scribe.render(verify_results.bad_results))
    if dump:
      print 'GOT RESULTS:\n{0}\n'.format(scribe.render(verify_results))
      print '\nEXPECTED:\n{0}\n'.format(scribe.render(expect_results))

    self.assertEqual(expect_ok, ok, error_msg)
    if expect_results:
      self.assertEqual(expect_results, verify_results)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonValueObservationVerifierTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
