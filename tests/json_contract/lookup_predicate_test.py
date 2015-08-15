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

_LETTER_DICT = { 'a': 'A', 'b': 'B', 'z': 'Z' }
_NUMBER_DICT = { 'a' :1, 'b': 2, 'three': 3 }
_COMPOSITE_DICT = { 'letters': _LETTER_DICT, 'numbers': _NUMBER_DICT }


class JsonLookupTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0}\nGOT\n{1}'.format(a, b)
    super(JsonLookupTest, self).assertEqual(a, b, msg)

  def test_lookup_path_found(self):
    # Test top level find.
    result = jc.lookup_path(_LETTER_DICT, 'a')
    self.assertTrue(result)
    self.assertEqual('A', result.value)

    expect_result = jc.JsonFoundValueResult(
        valid=True, value='A', source=_LETTER_DICT, path='a',
        path_trace=[jc.PathValue('a', 'A')])
    self.assertEqual(expect_result, result)

    self.assertEqual('B', jc.lookup_path(_LETTER_DICT, 'b').value)
    self.assertEqual(1, jc.lookup_path(_NUMBER_DICT, 'a').value)

    # Test top multi-level.
    result = jc.lookup_path(_COMPOSITE_DICT, 'letters/a')
    self.assertEqual('A', result.value)

    expect_result = jc.JsonFoundValueResult(
        valid=True, value='A', source=_COMPOSITE_DICT, path='letters/a',
        path_trace=[jc.PathValue('letters', _LETTER_DICT),
                    jc.PathValue('a', 'A')])
    self.assertEqual(expect_result, result)

  def test_lookup_path_root_not_found(self):
    result = jc.lookup_path(_COMPOSITE_DICT, 'a')
    self.assertFalse(result)
    self.assertEqual(jc.JsonMissingPathResult(_COMPOSITE_DICT, 'a'), result)

  def test_lookup_path_nested_not_found(self):
    result = jc.lookup_path(_COMPOSITE_DICT, 'letters/x')
    expect_path_trace = [jc.PathValue('letters', _LETTER_DICT)]
    self.assertEqual(expect_path_trace, result.path_trace)
    self.assertEqual('x', result.path)
    self.assertEqual(_LETTER_DICT, result.source)
    self.assertEqual(
      jc.JsonMissingPathResult(_LETTER_DICT, 'x', path_trace=expect_path_trace),
      result)

  def test_lookup_path_found_in_list(self):
    source = [_NUMBER_DICT, _COMPOSITE_DICT]
    result = jc.lookup_path(source, 'letters/b')
    self.assertTrue(result)
    self.assertEqual('B', result.value)
    expect_result = jc.JsonFoundValueResult(
        valid=True, value='B', source=source, path='letters/b',
        path_trace=[jc.PathValue('letters', _LETTER_DICT),
                    jc.PathValue('b', 'B')])
    self.assertEqual(expect_result, result)

    source = [_LETTER_DICT, _COMPOSITE_DICT]
    result = jc.lookup_path(source, 'numbers/b')
    self.assertEqual(2, result.value)
    expect_result = jc.JsonFoundValueResult(
        valid=True, value=2, source=source, path='numbers/b',
        path_trace=[jc.PathValue('numbers', _NUMBER_DICT),
                    jc.PathValue('b', 2)])
    self.assertEqual(expect_result, result)

  def test_lookup_path_not_found_in_list(self):
    result = jc.lookup_path(_COMPOSITE_DICT, 'letters/x')
    self.assertFalse(result)
    expect_result = jc.JsonMissingPathResult(
        _LETTER_DICT, 'x',
        path_trace=[jc.PathValue('letters', _LETTER_DICT)])
    self.assertEqual(expect_result, result)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonLookupTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
