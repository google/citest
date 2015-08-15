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
import citest.json_contract as jc


_LETTER_DICT = { 'a':'A', 'b':'B', 'z':'Z' }
_NUMBER_DICT = { 'a':1, 'b':2, 'three':3 }
_MIXED_DICT  = {'a':'A', 'b':2, 'x':'X'}


class JsonObserverTest(unittest.TestCase):
  def test_observation(self):
    observation = jc.Observation()
    self.assertEqual([], observation.errors)
    self.assertEqual([], observation.objects)

    expect = jc.Observation()
    self.assertEqual(expect, observation)

    observation.add_error(jc.PredicateResult(False))
    self.assertNotEqual(expect, observation)

    expect.add_error(jc.PredicateResult(False))
    self.assertEqual(expect, observation)

    observation = jc.Observation()
    expect = jc.Observation()

    observation.add_object('A')
    self.assertNotEqual(expect, observation)
    self.assertEqual(['A'], observation.objects)

    expect.add_object('A')
    self.assertEqual(expect, observation)

    observation.add_object('B')
    self.assertNotEqual(expect, observation)
    self.assertEqual(['A', 'B'], observation.objects)

    expect = jc.Observation()
    expect.add_all_objects(['A', 'B'])
    self.assertEqual(expect, observation)

    observation.add_object(['C'])
    self.assertEqual(observation.objects, ['A', 'B', ['C']])
    expect = jc.Observation()
    expect.add_all_objects(['A', 'B', ['C']])
    self.assertEqual(expect, observation)

    expect = observation
    observation = jc.Observation()
    observation.extend(expect)
    self.assertEqual(expect, observation)


  def test_object_observer_map(self):
    # Test no filter.
    observer = jc.ObjectObserver()
    observation = jc.Observation()
    expected = jc.Observation()
    expected.add_object(_NUMBER_DICT)
    observer.filter_all_objects_to_observation([_NUMBER_DICT], observation)
    self.assertEqual([_NUMBER_DICT], observation.objects)
    self.assertEqual(expected, observation)

    pred_list = [jc.PathEqPredicate('a', 'A'), jc.PathEqPredicate('b', 'B')]
    conjunction = jc.ConjunctivePredicate(pred_list)
    observer = jc.ObjectObserver(conjunction)
    observation = jc.Observation()

    expected = jc.Observation()
    expected.add_object(_LETTER_DICT)
    observer.filter_all_objects_to_observation([_LETTER_DICT], observation)
    self.assertEqual([_LETTER_DICT], observation.objects)
    self.assertEqual(expected, observation)

    observation = jc.Observation()
    expected = jc.Observation()
    expected.add_object(_LETTER_DICT)
    expected.add_object(_LETTER_DICT)
    observer.filter_all_objects_to_observation(
        [_LETTER_DICT, _NUMBER_DICT, _LETTER_DICT], observation)
    self.assertEqual([_LETTER_DICT, _LETTER_DICT], observation.objects)

    observation = jc.Observation()
    expected = jc.Observation()
    observer.filter_all_objects_to_observation([_NUMBER_DICT], observation)
    self.assertEqual([], observation.objects)
    # Note that filtering doesnt observe errors.
    self.assertEqual(expected, observation)

  def test_observation_strict_vs_nonstrict(self):
    aA = jc.PathEqPredicate('a', 'A')
    bB = jc.PathEqPredicate('b', 'B')

    unstrict_object_list = [_NUMBER_DICT, _LETTER_DICT, _MIXED_DICT]
    unstrict_observation = jc.Observation()
    unstrict_observation.add_all_objects(unstrict_object_list)

    strict_object_list = [_LETTER_DICT, { 'a':'A', 'b':'B', 'x':'X' }]
    strict_observation = jc.Observation()
    strict_observation.add_all_objects(strict_object_list)

    none_object_list = [_NUMBER_DICT, _MIXED_DICT]
    none_observation = jc.Observation()
    none_observation.add_all_objects(none_object_list)

    test_cases = [
      #  Name      jc.Observation        Strict,  Unstrict
      #---------------------------------------------------
      ('Strict',   strict_observation,   True,    True),
      ('Unstrict', unstrict_observation, False,   True),
      ('None',     none_observation,     False,   False)
    ]

    # For each of the cases, test it with strict and non-strict verification.
    for test in test_cases:
      name = test[0]
      observation = test[1]

      # For this case, check it strict (2) and unstrict (3).
      for index in [2, 3]:
        test_strict = index == 2
        expected = test[index]
        verifier = jc.ValueObservationVerifier(
          title='Verifier', constraints=[aA, bB], strict=test_strict)

        verify_result = verifier(observation)
        try:
          self.assertEqual(expected, verify_result.__nonzero__())
        except Exception as e:
          print '*** FAILED case={0}:\n{1}'.format(name, e)
          print 'GOT {0}'.format(verify_result)
          raise


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonObserverTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
