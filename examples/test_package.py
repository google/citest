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
import subprocess
import time
import unittest
from citest.base.test_package import run_all_tests_in_dir
from citest.base import TestRunner
import __main__


def spawn_all_tests_in_dir(dirname=None, recurse=False, concurrent=True):
  start_time = time.time()
  if not dirname:
    dirname = os.path.dirname(__main__.__file__)
  glob_path = '**/*_test.py' if recurse else '*_test.py'
  files = glob.glob('{0}/{1}'.format(dirname, glob_path))

  args = ''
  test_modules = []
  subprocesses = {}
  failures = 0
  for script in files:
    test_modules.append(os.path.basename(script)[:-3])  # strip off .py suffix
    print 'Starting "{0}"'.format(script)
    test = subprocess.Popen('python {0} {1}'.format(script, args), shell=True)
    if concurrent:
      subprocesses[test] = test
    else:
      code = test.wait()
      if code != 0:
        failures += 1

  for script,test in subprocesses.items():
    code = test.poll()
    if code is None:
      print 'Waiting for "{0}"'.format(test)
      code = test.wait()
    if code != 0:
      failures += 1
  end_time = time.time()

  print '=' * 40
  print 'Ran %d scripts in %.3fs' % (len(test_modules), end_time - start_time)
  if failures:
    print '\nFAILED  {0} of {1}'.format(failures, len(test_modules))
  else:
    print '\nSUCCESS'

  return failures


import sys
if __name__ == '__main__':
  sys.exit(spawn_all_tests_in_dir(None, True))
