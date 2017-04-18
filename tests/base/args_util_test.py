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

import citest.base.args_util as args_util


class ArgsUtilTest(unittest.TestCase):
  def test_replace(self):
    dict = {'ONE': 'one', 'TWO': 'two'}

    identity = 'Identity string'
    self.assertEqual(identity, args_util.replace(identity, dict))

    closed = 'ONE=$ONE, TWO=$TWO'
    self.assertEqual('ONE=one, TWO=two', args_util.replace(closed, dict))

    open = 'ONE=$ONE, THREE=$THREE'
    self.assertEqual('ONE=one, THREE=$THREE', args_util.replace(open, dict))


if __name__ == '__main__':
  unittest.main()
