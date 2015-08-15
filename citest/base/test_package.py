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

import glob
import os
import os.path
import unittest
import __main__

def collect_suites_in_dir(dir):
  """Collect all the tests in the given directory.

  Args:
    dir: The directory to search in.

  Returns:
    A list of test suites loaded from all the modules named *_test.py in dir.
  """
  prefix = dir.replace('/', '.') + '.'
  test_file_names = glob.glob(dir + '/*_test.py')
  module_names = [os.path.basename(test_file[0:-3])
                  for test_file in test_file_names]
  if not module_names:
    return []
  
  return [unittest.defaultTestLoader.loadTestsFromName(prefix + test_file)
          for test_file in module_names]


def run_all_tests_in_dir(dir=None, recurse=False):
  """Run all the *_test.py files in the provided directory.

  Args:
    dir: Path to directory containing tests. If not defined, use the directory
        that the __main__.__file__ is in.
    recurse: True if should recurse the directory tree for all the tests.
  """
  if not dir:
    dir = os.path.dirname(__main__.__file__)

  if recurse:
    suites = []
    for dir_name, subdir_list, file_list in os.walk(dir):
        suites.extend(collect_suites_in_dir(dir_name))
  else:
    suites = collect_suites_in_dir(dir)

  testSuite = unittest.TestSuite(suites)
  text_runner = unittest.TextTestRunner(verbosity=2).run(testSuite)
