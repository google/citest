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
from json import JSONDecoder
from citest.base import JsonScrubber

class JsonScrubberTest(unittest.TestCase):
  def test_string(self):
      scrubber = JsonScrubber()
      self.assertEqual('Hello', scrubber('Hello'))
      self.assertEqual('password is 1234', scrubber('password is 1234'))

  def test_dict_ok(self):
      scrubber = JsonScrubber()
      d = {'A': 'a', 'B': 'b'}
      self.assertEqual(d, scrubber(d))
      
  def test_dict_secret(self):
      scrubber = JsonScrubber()
      d = {'A': 'a', 'secret': 'secret'}
      self.assertEqual({'A': 'a', 'secret': scrubber.REDACTED}, scrubber(d))
      
  def test_dict_password(self):
      scrubber = JsonScrubber()
      d = {'A': 'a', 'password': 'p'}
      self.assertEqual({'A': 'a', 'password': scrubber.REDACTED}, scrubber(d))
  
  def test_key_value(self):
      scrubber = JsonScrubber()
      l = [{'key': 'apassword', 'value': 'p'},
           {'key': 'asecret', 'value': 's'},
           {'key': 'plain', 'value': 'v'}]
      self.assertEqual([{'key': 'apassword', 'value': scrubber.REDACTED},
                        {'key': 'asecret', 'value': scrubber.REDACTED},
                        {'key': 'plain', 'value': 'v'}],
                       scrubber(l))
  
  def test_dict_substring(self):
      scrubber = JsonScrubber()
      d = {'asecrets': 'a', 'apasswords': 'p'}
      self.assertEqual({'asecrets': scrubber.REDACTED,
                        'apasswords': scrubber.REDACTED},
                       scrubber(d))
 
  def test_dict_nested(self):
      scrubber = JsonScrubber()
      d = {'parent': {'A': 'a', 'secret': 'secret'}}
      self.assertEqual({'parent': {'A': 'a', 'secret': scrubber.REDACTED}},
                       scrubber(d))

  def test_list(self):
      scrubber = JsonScrubber()
      l = [{'secrets': 'a'}, {'passwords': 'p'}, {'a': 'A'}]
      self.assertEqual([{'secrets': scrubber.REDACTED},
                        {'passwords': scrubber.REDACTED},
                        {'a': 'A'}],
                       scrubber(l))

  def test_value(self):
    scrubber = JsonScrubber()
    d = {'A': '---BEGIN PRIVATE KEY---\nABC\n123+/==\n---END PRIVATE KEY---\n'}
    self.assertEqual({'A': scrubber.REDACTED}, scrubber(d))

  def test_json(self):
    text = u"""[
  {{
    "canIpForward": false,
    "cpuPlatform": "Intel Ivy Bridge",
    "creationTimestamp": "2015-11-03T08:38:59.701-08:00",
    "description": "",
    "metadata": {{
      "fingerprint": "p_LMICy68MQ=",
      "items": [
        {{
          "key": "google-cloud-marketplace-solution-key",
          "value": "bitnami-launchpad:jenkins"
        }},
        {{
          "key": "google-cloud-marketplace-generate-password",
          "value": "{type}"
        }},
        {{
          "key": "bitnami-base-password",
          "value": "{password}"
        }}
      ],
      "kind": "compute#metadata"
    }}
  }}
]"""

    decoder = JSONDecoder()
    scrubber = JsonScrubber()
    original = text.format(type='bitnami-base-password', password='B1a6xwpS')
    expect = decoder.decode(text.format(type=scrubber.REDACTED,
                                        password=scrubber.REDACTED))

    self.assertEqual(expect, decoder.decode(scrubber(original)))


if __name__ == '__main__':
  unittest.main()
