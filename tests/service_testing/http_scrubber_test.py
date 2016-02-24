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
import citest.service_testing as st
from citest.base import JsonScrubber


class HttpScrubberTest(unittest.TestCase):
  _TEST_AUTH_KEY = 'aUtHoRiZaTiOn'
  _ORIGINAL_AUTH_VALUE = 'Basic TheBase64EncodedValueIsHere'
  _CENSORED_AUTH_VALUE = 'Basic ' + st.DefaultHttpHeadersScrubber.REDACTED

  _ORIGINAL_AUTH_HEADER = {_TEST_AUTH_KEY: _ORIGINAL_AUTH_VALUE}
  _CENSORED_AUTH_HEADER = {_TEST_AUTH_KEY: _CENSORED_AUTH_VALUE}

  _TEST_ORIGINAL_HEADERS = {'GoodHeader': 'GoodValue',
                            'Content-Type': 'text',
                            _TEST_AUTH_KEY: _ORIGINAL_AUTH_VALUE}
  _TEST_CENSORED_HEADERS = {'GoodHeader': 'GoodValue',
                            'Content-Type': 'text',
                            _TEST_AUTH_KEY: _CENSORED_AUTH_VALUE}

  def test_default_header_scrubber(self):
     original_headers = dict(self._TEST_ORIGINAL_HEADERS)
     got_headers = st.DefaultHttpHeadersScrubber()(original_headers)
     self.assertEquals(self._TEST_CENSORED_HEADERS, got_headers)
     self.assertEquals(self._TEST_CENSORED_HEADERS, original_headers)

  def test_default_http_scrubber(self):
     scrubber = st.HttpScrubber()
     original_headers = dict(self._TEST_ORIGINAL_HEADERS)
     got_headers = scrubber.scrub_headers(original_headers)
     self.assertEquals(self._TEST_CENSORED_HEADERS, got_headers)
     self.assertEquals(self._TEST_CENSORED_HEADERS, original_headers)

     payload = {'password': 'VALUE', 'secret': 'VALUE', 'private': 'VALUE'}
     expect = dict(payload)
     self.assertEquals(expect, scrubber.scrub_request(payload))
     self.assertEquals(expect, payload)
     self.assertEquals(expect, scrubber.scrub_response(payload))
     self.assertEquals(expect, payload)

     url = 'http://path?password=VALUE'
     self.assertEquals(url, scrubber.scrub_url(url))
     
  def test_http_scrubber(self):
     json_scrubber = JsonScrubber()
     scrubber = st.HttpScrubber(headers_scrubber=None,
                                request_scrubber=json_scrubber,
                                response_scrubber=json_scrubber)
     original_headers = dict(self._TEST_ORIGINAL_HEADERS)
     got_headers = scrubber.scrub_headers(original_headers)
     self.assertEquals(self._TEST_CENSORED_HEADERS, got_headers)
     self.assertEquals(self._TEST_CENSORED_HEADERS, original_headers)

     # verify case insensitive json attribute scrubbing
     payload = {'PassWord': 'XYZ', 'sEcReT': 'X', 'priVate': 'VALUE',
                'whatever' : 'secret'}
     redacted = json_scrubber.REDACTED
     expect = {'PassWord': redacted,
               'sEcReT': redacted,
               'priVate': redacted,
               'whatever' : 'secret'}
     # The scrubber scrubs the original for extra safety.
     actual_payload = dict(payload)
     self.assertEquals(expect, scrubber.scrub_request(actual_payload))
     self.assertEquals(expect, actual_payload)
     actual_payload = dict(payload)
     self.assertEquals(expect, scrubber.scrub_response(actual_payload))
     self.assertEquals(expect, actual_payload)

     url = 'http://path?password=VALUE'
     self.assertEquals(url, scrubber.scrub_url(url))
     

if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(HttpScrubberTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
