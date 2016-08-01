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

import unittest

from citest.base.execution_context import ExecutionContext


class ExecutionContextTest(unittest.TestCase):
  def test_eval(self):
    context = ExecutionContext()
    context.add_internal('i', 'I')
    context.add_snapshotable('x', 'X')
    fn = lambda ctxt: '{0}{1}'.format(ctxt['i'], ctxt['x'])

    self.assertEqual('i', context.eval('i'))
    self.assertEqual(True, context.eval(True))
    self.assertEqual(123, context.eval(123))
    self.assertEqual('IX', context.eval(fn))


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(ExecutionContextTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
