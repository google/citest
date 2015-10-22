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


import argparse
import os.path
import sys
import __main__

from citest.base import BaseTestCase
from citest.base import TestRunner


tested_main = False

class TestRunnerTest(BaseTestCase):
  def test_main(self):
    # Confirms that our tests run.
    global tested_main
    tested_main = True

  def test_init_argument_parser(self):
    parser = argparse.ArgumentParser()
    TestRunner.global_runner().initArgumentParser(parser)
    args = parser.parse_args()
    self.assertEquals(args.log_dir, '.')
    self.assertEquals(
      args.log_filename,
      os.path.basename(__main__.__file__.replace('.py', '.log')))

  def test_bindings(self):
    self.assertEquals('.', TestRunner.global_runner().bindings['LOG_DIR'])
    self.assertEquals(
      os.path.basename(__main__.__file__.replace('.py', '.log')),
      TestRunner.global_runner().bindings['LOG_FILENAME'])


if __name__ == '__main__':
  result = TestRunner.main(test_case_list=[TestRunnerTest])
  if not tested_main:
     raise Exception("Test Failed.")

  sys.exit(result)
