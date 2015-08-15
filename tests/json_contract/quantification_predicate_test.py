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

_LETTER_ARRAY = ['a', 'b', 'c']
_LETTER_DICT = {'a': 'A', 'b': 'B', 'z': 'Z'}
_NUMBER_DICT = {'a': 1, 'b': 2, 'three': 3}


def _good_result(value, pred):
  """Constructs a JsonFoundValueResult where pred returns value as valid."""
  return jc.JsonFoundValueResult(value=value, pred=pred, valid=True)


def _bad_result(value, pred):
  """Constructs a JsonFoundValueResult where pred returns value as invalid."""
  return jc.JsonFoundValueResult(value=value, pred=pred, valid=False)

def _append_good_result(builder, expect_value, pred):
  builder.append_result(_good_result(expect_value, pred))

def _append_bad_result(builder, expect_value, pred):
  builder.append_result(_bad_result(expect_value, pred))


class JsonQuantificationPredicateTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0}\n\nGOT\n{1}'.format(a, b)
    super(JsonQuantificationPredicateTest, self).assertEqual(a, b, msg)

  def assertBadResult(self, builder, result):
    self.assertEqual(builder.build(False), result)

  def assertGoodResult(self, builder, result):
    self.assertEqual(builder.build(True), result)

  ############
  # EXISTS_EQ
  ############
  def test_existential_eq_one_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_EQ('a banana'))
    _append_good_result(builder, 'a banana', jc.STR_EQ('a banana'))
    self.assertGoodResult(builder, jc.EXISTS_EQ('a banana')(value))

  def test_existential_eq_many_of(self):
    value = ['an apple', 'an apple']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_EQ('an apple'))
    _append_good_result(builder, 'an apple', jc.STR_EQ('an apple'))
    _append_good_result(builder, 'an apple', jc.STR_EQ('an apple'))
    self.assertGoodResult(builder, jc.EXISTS_EQ('an apple')(value))

  def test_existential_eq_none_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_EQ('bananas'))
    _append_bad_result(builder, 'an apple', jc.STR_EQ('bananas'))
    _append_bad_result(builder, 'a banana', jc.STR_EQ('bananas'))
    self.assertBadResult(builder, jc.EXISTS_EQ('bananas')(value))

  def test_existential_eq_not_partial(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_EQ('an'))
    _append_bad_result(builder, 'an apple', jc.STR_EQ('an'))
    _append_bad_result(builder, 'a banana', jc.STR_EQ('an'))
    self.assertBadResult(builder, jc.EXISTS_EQ('an')(value))

  ############
  # EXISTS_NE
  ############
  def test_existential_ne_all_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_NE('bananas'))
    _append_good_result(builder, 'an apple', jc.STR_NE('bananas'))
    _append_good_result(builder, 'a banana', jc.STR_NE('bananas'))
    self.assertGoodResult(builder, jc.EXISTS_NE('bananas')(value))

  def test_existential_ne_one_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_NE('a banana'))
    _append_good_result(builder, 'an apple', jc.STR_NE('a banana'))
    self.assertGoodResult(builder, jc.EXISTS_NE('a banana')(value))

  def test_existential_ne_none_of(self):
    value = ['an apple', 'an apple']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_NE('an apple'))
    _append_bad_result(builder, 'an apple', jc.STR_NE('an apple'))
    _append_bad_result(builder, 'an apple', jc.STR_NE('an apple'))
    self.assertGoodResult(builder, jc.EXISTS_NE('an apple')(value))

  ##################
  # EXISTS_CONTAINS
  ##################
  def test_existential_contains_one_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_CONTAINS('a banana'))
    _append_good_result(builder, 'a banana', jc.STR_SUBSTR('a banana'))
    self.assertGoodResult(builder, jc.EXISTS_CONTAINS('a banana')(value))

  def test_existential_contains_all_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_CONTAINS('an'))
    _append_good_result(builder, 'an apple', jc.STR_SUBSTR('an'))
    _append_good_result(builder, 'a banana', jc.STR_SUBSTR('an'))
    self.assertGoodResult(builder, jc.EXISTS_CONTAINS('an')(value))

  def test_existential_contains_none_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_CONTAINS('bananas'))
    _append_bad_result(builder, 'an apple', jc.STR_SUBSTR('bananas'))
    _append_bad_result(builder, 'a banana', jc.STR_SUBSTR('bananas'))
    self.assertBadResult(builder, jc.EXISTS_CONTAINS('bananas')(value))

  def test_existential_contains_partial(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.EXISTS_CONTAINS('ap'))
    _append_good_result(builder, 'an apple', jc.STR_SUBSTR('ap'))
    self.assertGoodResult(builder, jc.EXISTS_CONTAINS('ap')(value))


  #########
  # ALL_EQ
  #########
  def test_universal_eq_all_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_EQ('abc'))
    _append_good_result(builder, 'abc', jc.STR_EQ('abc'))
    _append_good_result(builder, 'abc', jc.STR_EQ('abc'))
    self.assertGoodResult(builder, jc.ALL_EQ('abc')(['abc', 'abc']))

  def test_universal_eq_one_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_EQ('a banana'))
    _append_bad_result(builder, 'an apple', jc.STR_EQ('a banana'))
    _append_good_result(builder, 'a banana', jc.STR_EQ('a banana'))
    self.assertBadResult(builder, jc.ALL_EQ('a banana')(value))

  def test_universal_eq_none_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_EQ('an'))
    _append_bad_result(builder, 'an apple', jc.STR_EQ('an'))
    _append_bad_result(builder, 'a banana', jc.STR_EQ('an'))
    self.assertBadResult(builder, jc.ALL_EQ('an')(value))


  #########
  # ALL_NE
  #########
  def test_universal_ne_all_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_NE('an'))
    _append_good_result(builder, 'an apple', jc.STR_NE('an'))
    _append_good_result(builder, 'a banana', jc.STR_NE('an'))
    self.assertGoodResult(builder, jc.ALL_NE('an')(value))

  def test_universal_ne_one_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_NE('a banana'))
    _append_good_result(builder, 'an apple', jc.STR_NE('a banana'))
    _append_bad_result(builder, 'a banana', jc.STR_NE('a banana'))
    self.assertBadResult(builder, jc.ALL_NE('a banana')(value))

  def test_universal_ne_none_of(self):
    value = ['an apple', 'an apple']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_NE('an apple'))
    _append_bad_result(builder, 'an apple', jc.STR_NE('an apple'))
    _append_bad_result(builder, 'an apple', jc.STR_NE('an apple'))
    self.assertBadResult(builder, jc.ALL_NE('an apple')(value))

  ###############
  # ALL_CONTAINS
  ###############
  def test_universal_contains_all_of(self):
    value = ['an apple', 'a banana']
    builder = jc.CompositePredicateResultBuilder(jc.ALL_CONTAINS('an'))
    _append_good_result(builder, 'an apple', jc.STR_SUBSTR('an'))
    _append_good_result(builder, 'a banana', jc.STR_SUBSTR('an'))
    self.assertGoodResult(builder, jc.ALL_CONTAINS('an')(value))


  def test_universal_contains_some_of(self):
    value = ['an apple', 'a banana', 'oranges']

    builder = jc.CompositePredicateResultBuilder(jc.ALL_CONTAINS('ap'))
    _append_good_result(builder, 'an apple', jc.STR_SUBSTR('ap'))
    _append_bad_result(builder, 'a banana', jc.STR_SUBSTR('ap'))
    _append_bad_result(builder, 'oranges', jc.STR_SUBSTR('ap'))
    self.assertBadResult(builder,  jc.ALL_CONTAINS('ap')(value))


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonQuantificationPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
