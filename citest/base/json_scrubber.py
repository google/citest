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

"""Implements a JsonScrubber to remove sensitive data from a JSON document."""

import re
from json import JSONDecoder
from json import JSONEncoder


class JsonScrubber(object):
  """Scrubber to redact output from content."""

  REDACTED = '*' * 5

  def __init__(self, regex='(?i)(?:password|secret|private)'):
    self.__re = re.compile(regex)

    base64 = '[a-zA-Z0-9+/\n]'
    pad = '(?:=|\u003d)'
    begin_marker = '-+BEGIN [A-Z0-9 ]*KEY-+'
    end_marker = '-+END [A-Z0-9 ]*KEY-+'
    self.__key_re = re.compile('(?ms){begin}\n{base64}+{pad}*\n{end}\n'.format(
        begin=begin_marker, base64=base64, pad=pad, end=end_marker))


  def process_text(self, value):
    """Scrub text.
    Args:
      value: [string] The value to scrub.
    Returns:
      scrubbed value.
    """
    match = self.__key_re.search(value)
    if not match:
      return value

    return self.REDACTED

  def process_list(self, l):
    """Scrub elements of a list.

    Args:
      l: [list] The list to redact from.

    Returns:
      Redacted list.
    """
    result = []
    for e in l:
       # pylint: disable=bad-indentation
       if isinstance(e, dict):
         result.append(self.process_dict(e))
       elif isinstance(e, list):
         result.append(self.process_list(e))
       else:
         result.append(e)
    return result

  def process_dict(self, d):
    """Scrub elements of a dictionary.

    Args:
      d: [dict] The dictionary to redact from.

    Returns:
      Redacted dict.
    """
    if len(d) == 2:
        # pylint: disable=bad-indentation
        keys = d.keys()
        if 'key' in keys and 'value' in keys:
          match = self.__re.search(d['key'])

          if match:
            d['value'] = self.REDACTED

    for name, value in d.items():
        # pylint: disable=bad-indentation
        match = self.__re.search(name)
        if match:
          d[name] = self.REDACTED
        elif isinstance(value, list):
          d[name] = self.process_list(value)
        elif isinstance(value, dict):
          d[name] = self.process_dict(value)
        elif isinstance(value, basestring):
          d[name] = self.process_text(value)
    return d

  def __call__(self, data):
    """Scrub data.

    Args:
      data: The data to scrub.

    Returns:
      Redacted data.
    """
    if isinstance(data, dict):
      return self.process_dict(data)
    if isinstance(data, list):
      return self.process_list(data)
    if isinstance(data, basestring):
      try:
        value = JSONDecoder().decode(data)
        scrubbed_value = self(value)
        return JSONEncoder().encode(scrubbed_value)
      except (TypeError, ValueError):
        pass

    return data
