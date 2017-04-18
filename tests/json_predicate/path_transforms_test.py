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


"""Tests the citest.json_predicate.path_transforms module."""


import unittest

from citest.base import ExecutionContext
from citest.json_predicate import FieldDifference


class PathTransformTest(unittest.TestCase):
  def assertEqual(self, a, b, msg=''):
    if not msg:
      msg = 'EXPECTED\n{0!r}\nGOT\n{1!r}'.format(a, b)
    super(PathTransformTest, self).assertEqual(a, b, msg)

  def test_field_difference_eq(self):
    orig = FieldDifference('X', 'Y')
    same = FieldDifference('X', 'Y')
    diff = FieldDifference('Y', 'X')
    self.assertEqual(orig, same)
    self.assertNotEqual(orig, diff)

  def test_field_difference(self):
    context = ExecutionContext()
    source = {'a': 7, 'b': 4}
    xform = FieldDifference('a', 'b')
    self.assertEqual(3, xform(context, source))

  def test_field_difference_indirect(self):
    context = ExecutionContext()
    source = {'a': 7, 'b': 4}
    xform = FieldDifference(lambda x: 'b', lambda x: 'a')
    self.assertEqual(-3, xform(context, source))


if __name__ == '__main__':
  unittest.main()
