# Copyright 2018 Google Inc. All Rights Reserved.
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

"""Test HttpResponsePredicate"""

import unittest

from citest.base import ExecutionContext

from citest.service_testing import (
    HttpResponsePredicate,
    HttpResponseType)


class HttpResponsePredicateTest(unittest.TestCase):
  def test_response_ok(self):
    tests = [(200, None, HttpResponseType(http_code=200, output='OK')),
             (None, 'OK', HttpResponseType(http_code=200, output='OK')),
             (404, None, HttpResponseType(http_code=404, output='NOT_FOUND')),
             (200, '^(?i)not found$',
              HttpResponseType(http_code=200, output='NOT FOUND')),
             (200, '(?i)not found',
              HttpResponseType(http_code=200, output='NOT FOUND')),
             (None, '(?i)not found',
              HttpResponseType(http_code=404, output='file not found!'))]
    for want_code, want_regex, have_response in tests:
      context = ExecutionContext()
      predicate = HttpResponsePredicate(
          http_code=want_code, content_regex=want_regex)
      result = predicate(context, have_response)
      self.assertTrue(result)
      self.assertEquals(have_response, result.value)

  def test_response_bad(self):
    tests = [(201, None, HttpResponseType(http_code=200, output='OK')),
             (None, 'OK', HttpResponseType(http_code=200, output='BAD')),
             (404, None, HttpResponseType(http_code=200, output='NOT_FOUND')),
             (200, '^not found$',
              HttpResponseType(http_code=200, output='NOT FOUND')),
             (200, 'not found',
              HttpResponseType(http_code=200, output='NOT FOUND')),
             (200, 'not found',
              HttpResponseType(http_code=404, output='file not found!'))]
    for want_code, want_regex, have_response in tests:
      context = ExecutionContext()
      predicate = HttpResponsePredicate(
          http_code=want_code, content_regex=want_regex)
      result = predicate(context, have_response)
      self.assertFalse(result)
      self.assertEquals(have_response, result.value)


if __name__ == '__main__':
  unittest.main()
