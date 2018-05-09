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

"""Interface for scrubbing sensitive information when logging HTTP actions."""
# pylint: disable=too-few-public-methods


class IdentityScrubber(object):
  """The identity scrubber returns the original content."""

  def __call__(self, value):
    return value


class DefaultHttpHeadersScrubber(object):
  """The default HTTP header scrubber redacts standard headers.

  The recognized headers are:
    Authorization
  """

  REDACTED = '*' * 5

  def __call__(self, headers):
    # Headers are case-insensitive
    for key, value in headers.items():
      if key.lower() == 'authorization':
        # Leave format type if any, then redact remainder.
        headers[key] = value[:value.find(' ') + 1] + self.REDACTED

    return headers


class HttpScrubber(object):
  """Interface class for scrubbing HTTP messages."""

  def __init__(self,
               url_scrubber=None,
               headers_scrubber=None,
               request_scrubber=None,
               response_scrubber=None):
    """Constructor.

    Args:
      url_scrubber: [callable] If not None, returns scrubbed url from string.
      headers_scrubber: [callable] If not None, returns scrubbed header dict
          from dictionary containing the headers.
      request_scrubber: [callable] If not None, returns scrubbed request from
          request string. The request is the outbound HTTP payload.
      response_scrubber: [callable] If not None, returns scrubbed response from
          response string. The response is the inbound HTTP payload.
    """
    identity = IdentityScrubber()
    self.__url_scrubber = url_scrubber or identity
    self.__request_scrubber = request_scrubber or identity
    self.__response_scrubber = response_scrubber or identity
    self.__headers_scrubber = headers_scrubber or DefaultHttpHeadersScrubber()

  def scrub_url(self, url):
    """Redact sensitive components from the url, if any.

    Returns:
      Censored url depending on the bound url_scrubber.
    """
    return self.__url_scrubber(url)

  def scrub_headers(self, header_dict):
    """Redact sensitive headers from the header_dict, if any.

    This may return a copy of the header_dict. It will not modify the
    header_dict itself.

    Returns:
      A scrubbed header mapping dictionary.
    """
    return self.__headers_scrubber(header_dict)

  def scrub_request(self, data):
    """Redact sensitive content from the request data, if any.

    Returns:
      Censored data depending on the bound request_scrubber.
    """
    return self.__request_scrubber(data)

  def scrub_response(self, data):
    """Redact sensitive content from the response data, if any.

    Returns:
      Censored data depending on the bound response_scrubber.
    """
    return self.__response_scrubber(data)
