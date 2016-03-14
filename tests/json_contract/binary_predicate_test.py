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

from citest.base import JsonSnapshotHelper
import citest.json_contract as jc
import citest.json_contract.binary_predicate as bp


_LETTER_ARRAY = ['a', 'b', 'c']
_LETTER_DICT = {'a': 'A', 'b': 'B', 'z': 'Z'}
_NUMBER_DICT = {'a': 1, 'b': 2, 'three': 3}


def good_result(value, pred):
  """Constructs a JsonFoundValueResult where pred returns value as valid."""
  return jc.JsonFoundValueResult(value=value, pred=pred, valid=True)


def bad_result(value, pred):
  """Constructs a JsonFoundValueResult where pred returns value as invalid."""
  return jc.JsonFoundValueResult(value=value, pred=pred, valid=False)


class JsonBinaryPredicateTest(unittest.TestCase):
  def assertEqual(self, expect, have, msg=''):
    JsonSnapshotHelper.AssertExpectedValue(expect, have, msg)

  def assertGoodResult(self, expect_value, pred, got_result):
    """Assert that got_result is expect_value returned by pred as valid."""
    self.assertEqual(good_result(expect_value, pred), got_result)

  def assertBadResult(self, expect_value, pred, got_result):
    """Assert that got_result is expect_value returned by pred as invalid."""
    self.assertEqual(bad_result(expect_value, pred), got_result)

  def test_string_eq(self):
    eq_abc = bp.STR_EQ('abc')
    self.assertGoodResult('abc', eq_abc, eq_abc('abc'))
    self.assertBadResult('abcd', eq_abc, eq_abc('abcd'))

  def test_string_ne(self):
    ne_abc = bp.STR_NE('abc')
    self.assertGoodResult('abcd', ne_abc, ne_abc('abcd'))
    self.assertBadResult('abc', ne_abc, ne_abc('abc'))

  def test_factory_type_mismatch(self):
    factory = bp.StandardBinaryPredicateFactory(
        '==', lambda a, b: True, operand_type=basestring)
    try:
      self.assertFalse(factory(['not a string']), "Expected type error")
    except TypeError as e:
      pass

    pred = factory('is a string')
    self.assertTrue(pred('ok'))

  def test_string_substr(self):
    substr_q = bp.STR_SUBSTR('q')
    substr_pqr = bp.STR_SUBSTR('pqr')
    self.assertGoodResult('pqr', substr_q, substr_q('pqr'))
    self.assertGoodResult('rqp', substr_q, substr_q('rqp'))
    self.assertGoodResult('pqr', substr_pqr, substr_pqr('pqr'))
    self.assertBadResult('abc', substr_q, substr_q('abc'))
    self.assertBadResult('xyz', substr_q, substr_q('xyz'))

  def operand_type_mismatch_error_helper(self, expected_type, factory,
                                         good_operand, bad_operand):
    """Helper method used to generate operand type mismatch errors.

    Args:
      factory: The factory to test.
      good_operand: A good operand value.
      bad_operand: A bad operand value.
    """
    try:
      self.assertFalse(factory(bad_operand), "Expected type error.")
    except TypeError:
      pass

    pred = factory(good_operand)
    try:
      self.assertEqual(
        jc.JsonTypeMismatchResult(
          expected_type, bad_operand.__class__, bad_operand),
        pred(bad_operand))
    except:
      print '\nFAILED value={0} pred={1}'.format(good_operand, pred.name)
      raise


  def operand_type_mismatch_ok_helper(self, expected_type, factory,
                                      good_operand, bad_operand, valid):
    pred = factory(bad_operand)
    self.assertEqual(
            jc.JsonFoundValueResult(valid=valid, value=good_operand, pred=pred),
            pred(good_operand))

    pred = factory(good_operand)
    self.assertEqual(
            jc.JsonFoundValueResult(valid=valid, value=bad_operand, pred=pred),
            pred(bad_operand))

  def standard_operand_type_mismatch_helper(
      self, expected_type, factory, good_operand, bad_operand, valid):
    # The standard operators (e.g. STR_EQ) have strong type checking.
    # If we want to take this away, then set this to False.
    # This is here to make it easier to transition over since this is something
    # under active consideration.
    #
    # TODO(ewiseblatt): 20150722
    # Make a decision and take out the alternative paths.
    if True:
      self.operand_type_mismatch_error_helper(
          expected_type, factory, good_operand, bad_operand)
    else:
      self.operand_type_mismatch_ok_helper(
          expected_type, factory, good_operand, bad_operand, valid)

  def test_standard_string_operator_type_mismatch(self):
    for value in [['value'], {'a':'A'}, 1]:
      for factory in [bp.STR_EQ, bp.STR_NE]:
        self.standard_operand_type_mismatch_helper(
          basestring, factory, good_operand='test value', bad_operand=value,
          valid=factory == bp.STR_NE)

  def test_string_specific_operator_type_mismatch(self):
    operand='valid string operand.'
    for value in [['value'], {'a':'A'}, 1]:
      for factory in [bp.STR_SUBSTR]:
        self.operand_type_mismatch_error_helper(
            basestring, factory, operand, value)

  def test_dict_eq(self):
    operand = {'a': 'A', 'b': 'B'}
    eq_pred = bp.DICT_EQ(operand)

    self.assertBadResult(_LETTER_DICT, eq_pred, eq_pred(_LETTER_DICT))
    self.assertGoodResult(operand, eq_pred, eq_pred(operand))
    self.assertBadResult({'a': 'A'}, eq_pred, eq_pred({'a': 'A'}))

  def test_dict_ne(self):
    operand = {'a': 'A', 'b': 'B'}
    ne_pred = bp.DICT_NE(operand)

    self.assertGoodResult(_LETTER_DICT, ne_pred, ne_pred(_LETTER_DICT))
    self.assertBadResult(operand, ne_pred, ne_pred(operand))
    self.assertGoodResult({'a': 'A'}, ne_pred, ne_pred({'a': 'A'}))

  def test_dict_simple_subset(self):
    operand = {'a': 'A', 'b': 'B'}
    subset_pred = bp.DICT_SUBSET(operand)

    self.assertGoodResult(_LETTER_DICT, subset_pred, subset_pred(_LETTER_DICT))
    self.assertGoodResult(operand, subset_pred, subset_pred(operand))
    self.assertEqual(
        jc.JsonMissingPathResult(source={'a':'A'}, path='b'),
        subset_pred({'a':'A'}))

  def test_dict_nested_subset(self):
    small_dict = {'first':'Apple', 'second':'Banana'}
    small_subset_pred = bp.DICT_SUBSET(small_dict)

    big_dict = {'first':'Apple', 'second':'Banana', 'third':'Cherry'}

    self.assertGoodResult(
        big_dict, small_subset_pred, small_subset_pred(big_dict))

    small_nested_dict = {'outer':small_dict}
    small_nested_subset_pred = bp.DICT_SUBSET(small_nested_dict)

    big_nested_dict = {'outer':big_dict, 'another':big_dict}
    self.assertGoodResult(big_nested_dict, small_nested_subset_pred,
                          small_nested_subset_pred(big_nested_dict))

  def test_dict_nested_subset_exact_keys(self):
    small_dict = {'first':'Apple', 'second':'Banana'}
    small_nested_dict = {'outer':small_dict}

    # In dictionary we want exact key matches, not subkeys.
    operand = {'out':{'first':'Apple'}}
    subset_pred = bp.DICT_SUBSET(operand)
    self.assertEqual(
        jc.JsonMissingPathResult(small_nested_dict, 'out'),
        subset_pred(small_nested_dict))

    # In dictionary we want exact key matches, not subkeys.
    nested_operand = {'fir':'Apple'}
    operand = {'outer':nested_operand}
    subset_pred = bp.DICT_SUBSET(operand)
    self.assertEqual(
        jc.JsonMissingPathResult(small_nested_dict, 'outer/fir'),
        subset_pred(small_nested_dict))

  def test_dict_nested_subset_exact_values(self):
    small_dict = {'first':'Apple', 'second':'Banana'}
    small_nested_dict = {'outer':small_dict}

    # In dictionary we want exact matches of strings, not substrings.
    nested_operand = {'first':'A'}
    operand = {'outer':nested_operand}
    subset_pred = bp.DICT_SUBSET(operand)

    self.assertEqual(
        jc.JsonFoundValueResult(value='Apple',
                                source=small_nested_dict, path='outer/first',
                                valid=False, pred=jc.STR_EQ('A')),
        subset_pred(small_nested_dict))

  def test_dict_subset_with_array_elements(self):
    small_dict = {'a':['A'], 'b':[1,2]}
    big_dict = {'a':['A','B','C'], 'b':[1,2,3], 'c':['red','yellow']}
    small_nested_dict = {'first':small_dict}
    big_nested_dict = {'first':big_dict, 'second':big_dict}

    small_subset_pred = bp.DICT_SUBSET(small_dict)
    nested_subset_pred = bp.DICT_SUBSET(small_nested_dict)
    self.assertGoodResult(
        big_dict, small_subset_pred, small_subset_pred(big_dict))
    self.assertGoodResult(
        big_nested_dict, nested_subset_pred, nested_subset_pred(big_nested_dict))

  def test_standard_dict_operator_type_mismatch(self):
    operand = {'a': 'A'}
    for value in [['a'], 'a', 1]:
      for factory in [bp.DICT_EQ, bp.DICT_NE]:
        self.standard_operand_type_mismatch_helper(
          dict, factory, good_operand=operand, bad_operand=value,
          valid=factory == bp.DICT_NE)

  def test_dict_specific_operator_type_mismatch(self):
    operand = {'a': 'A'}
    for value in [['a'], 'a', 1]:
      for factory in [bp.DICT_SUBSET]:
        self.operand_type_mismatch_error_helper(
            dict, factory, operand, value)

  def test_list_eq(self):
    operand = ['b', 'a'] # Out of order.
    eq_pred = bp.LIST_EQ(operand)

    # Order of actual operand matters.
    self.assertGoodResult(['b', 'a'], eq_pred, eq_pred(['b', 'a']))
    self.assertBadResult(['a', 'b'], eq_pred, eq_pred(['a', 'b']))

    self.assertBadResult(['b', 'a', 'c'], eq_pred, eq_pred(['b', 'a', 'c']))
    self.assertBadResult(['b'], eq_pred,  eq_pred(['b']))

  def test_list_similar(self):
    operand = ['b', 'a']
    similar_pred = bp.LIST_SIMILAR(operand)

    # Order of actual operand does not matter for finding it.
    self.assertGoodResult(['b', 'a'], similar_pred, similar_pred(['b', 'a']))
    self.assertGoodResult(['a', 'b'], similar_pred, similar_pred(['a', 'b']))

    self.assertBadResult(['a', 'b', 'c'],
                         similar_pred,
                         similar_pred(['a', 'b', 'c']))
    self.assertBadResult(['b', 'a', 'c'],
                         similar_pred,
                         similar_pred(['b', 'a', 'c']))
    self.assertBadResult(['b'], similar_pred,  similar_pred(['b']))

  def test_list_ne(self):
    operand = ['b', 'a'] # Out of order.
    ne_pred = bp.LIST_NE(operand)

    self.assertGoodResult(operand + ['c'], ne_pred, ne_pred(operand + ['c']))
    self.assertBadResult(operand, ne_pred, ne_pred(operand))
    self.assertGoodResult(['b'], ne_pred, ne_pred(['b']))

  def test_list_subset(self):
    operand = ['b', 'a'] # Out of order.
    subset_pred = bp.LIST_SUBSET(operand)

    self.assertGoodResult(operand + ['x'], subset_pred,
                          subset_pred(operand + ['x']))
    self.assertGoodResult(operand, subset_pred, subset_pred(operand))
    self.assertBadResult(['b'], subset_pred, subset_pred(['b']))

  def test_list_of_dict_subset_nonstrict(self):
    operand = [{'a': 'A'}]
    subset_pred = bp.LIST_SUBSET(operand)

    self.assertGoodResult([{'a': 'A', 'b': 'B'}], subset_pred,
                          subset_pred([{'a': 'A', 'b': 'B'}]))
    self.assertGoodResult(operand, subset_pred, subset_pred(operand))
    self.assertBadResult([{'b': 'B'}], subset_pred, subset_pred([{'b': 'B'}]))

  def test_list_of_dict_subset_strict(self):
    operand = [{'a': 'A'}]
    subset_pred = bp.LIST_SUBSET(operand, strict=True)

    self.assertBadResult([{'a': 'A', 'b': 'B'}], subset_pred,
                          subset_pred([{'a': 'A', 'b': 'B'}]))
    self.assertGoodResult(operand, subset_pred, subset_pred(operand))
    self.assertBadResult([{'b': 'B'}], subset_pred, subset_pred([{'b': 'B'}]))

  def test_list_of_dict_member_nonstrict(self):
    operand = {'a': 'A'}
    member_pred = bp.LIST_MEMBER(operand)

    self.assertGoodResult([{'a': 'A', 'b': 'B'}], member_pred,
                          member_pred([{'a': 'A', 'b': 'B'}]))
    self.assertGoodResult([operand], member_pred, member_pred([operand]))
    self.assertBadResult([{'b': 'B'}], member_pred, member_pred([{'b': 'B'}]))

  def test_list_of_dict_member_strict(self):
    operand = {'a': 'A'}
    member_pred = bp.LIST_MEMBER(operand, strict=True)

    self.assertBadResult([{'a': 'A', 'b': 'B'}], member_pred,
                         member_pred([{'a': 'A', 'b': 'B'}]))
    self.assertGoodResult([operand], member_pred, member_pred([operand]))
    self.assertBadResult([{'b': 'B'}], member_pred, member_pred([{'b': 'B'}]))

  def test_standard_list_operator_type_mismatch(self):
    for value in [{'a':'A'}, 'a', 1]:
      for factory in [bp.LIST_EQ, bp.LIST_NE]:
        self.standard_operand_type_mismatch_helper(
          list, factory, good_operand=['test value'], bad_operand=value,
          valid=factory == bp.LIST_NE)

  def test_list_specific_operator_type_mismatch(self):
    operand = ['a', 'b']
    for value in [{'a':'A'}, 'a', 1]:
      for factory in [bp.LIST_SUBSET]:
        self.operand_type_mismatch_error_helper(
            list, factory, operand, value)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(JsonBinaryPredicateTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
