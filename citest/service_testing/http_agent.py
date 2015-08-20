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


import collections
import logging
import urllib2

from ..base.scribe import Scribable
from . import testable_agent


class HttpResponseType(collections.namedtuple('HttpResponseType',
                                              ['retcode', 'output', 'error']),
                       Scribable):
  """Holds the results from an HTTP message.

  Attributes:
    retcode: The HTTP response code (or -1 if failed to send).
    output: The HTTP response if successful (2xx response)
    error: The HTTP response or other error if request failed.
  """
  def __str__(self):
    return 'retcode={0} output={1!r} error={2!r}'.format(
      self.retcode, self.output, self.error)

  def _make_scribe_parts(self, scribe):
    label = 'Response Error' if self.error else 'Response Data'
    data = self.error if self.error else self.output
    return [scribe.build_part('HTTP Code', self.retcode),
            scribe.build_json_part(label, data)]


class HttpOperationStatus(testable_agent.AgentOperationStatus):
  """Specialization of AgentOperationStatus for HttpAgent operations.

  This class assumes generic synchronous HTTP requests. Services may
  still wish to refine this further. Especially if they use an additional
  protocol, such as returning references to asynchronous status updates.
  """
  @staticmethod
  def _is_ok(retcode):
    return retcode >= 200 and retcode < 300

  @property
  def finished(self):
    return True

  @property
  def finished_ok(self):
    return self._is_ok(self._http_response.retcode)

  @property
  def detail(self):
    return self._http_response.output

  @property
  def error(self):
    return self._http_response.error

  def __init__(self, operation, http_response):
    super(HttpOperationStatus, self).__init__(operation)
    self._http_response = http_response

  def __cmp__(self, response):
    return self._http_response.__cmp__(response._http_response)

  def __str__(self):
    return 'http_response={0}'.format(self._http_response)

  def set_http_response(self, http_response):
    self._http_response = http_response


class HttpAgent(testable_agent.TestableAgent):
  """A specialization of TestableAgent for interacting with HTTP services."""
  def __init__(self, address, protocol='http'):
    super(HttpAgent, self).__init__()
    self._protocol = protocol
    self._address = address

  def _make_scribe_parts(self, scribe):
    return ([scribe.build_part('URL Netloc', self._address)]
            + super(HttpAgent, self)._make_scribe_parts(scribe))

  def new_post_operation(self, title, path, data):
    """Acts as an AgentOperation factory.

    Args:
      title: See AgentOperation title
      path: The URL path to POST to. The Agent provides the network location.
      data: The HTTP payload to post to the server.

      TODO(ewiseblatt): Will need to add headers.
    """
    return HttpPostOperation(title, path, data, self)

  def _new_get_status(self, operation, http_response):
    """Acts as an OperationStatus factory for GET requests.

    This method is intended to be used internally and by subclasses, not
    by normal callers.

    Args:
      operation: The AgentOperation the status is for.
      http_response: The HttpResponseType from the original GET response.
    """
    return HttpOperationStatus(operation, http_response)

  def _new_post_status(self, operation, http_response):
    """Acts as an OperationStatus factory for POST requests.

    This method is intended to be used internally and by subclasses, not
    by normal callers.

    Args:
      operation: The AgentOperation the status is for.
      http_response: The HttpResponseType from the original POST response.
    """
    return HttpOperationStatus(operation, http_response)

  def _send_http_request(
    self, path, http_type, data=None, headers=None, trace=True):
    """Send an HTTP message.

    Args:
      path: The URL path to send to (without network location)
      http_type: The HTTP message type (e.g. POST)
      data: Data payload to send, if any.
      headers: Headers to write, if any.
      trace: True if should log request and response.

    Returns:
      HttpResponseType
    """
    if headers == None:
      headers = {}
    if path[0] == '/':
      path = path[1:]
    url = '{0}://{1}/{2}'.format(self._protocol, self._address, path)

    req = urllib2.Request(url)
    for key, value in headers.items():
      req.add_header(key, value)

    if trace:
      self.logger.debug('%s url=%s data=%s', http_type, url, data)

    output = None
    error = None
    try:
      response = urllib2.urlopen(req, data)
      code = response.getcode()
      output = response.read()
      if trace:
        self.logger.debug('  -> http=%d: %s', code, output)
    except urllib2.HTTPError as e:
      code = e.getcode()
      error = e.read()
      if trace:
        self.logger.debug('  -> http=%d: %s', code, error)
    except urllib2.URLError as e:
      if trace:
        self.logger.debug('  *** except: %s', e)
      code = -1
      error = str(e)
    return HttpResponseType(code, output, error)


  def post(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP POST."""
    return self._send_http_request(
      path, 'POST', data=data,
      headers={'Content-Type': content_type}, trace=trace)

  def get(self, path, trace=True):
    """Perform an HTTP GET."""
    return self._send_http_request(path, 'GET', trace=trace)


class HttpPostOperation(testable_agent.AgentOperation):
  """Specialization of AgentOperation that performs HTTP POST."""
  def __init__(self, title, path, data, http_agent=None):
    super(HttpPostOperation, self).__init__(title, http_agent)
    if http_agent and not isinstance(http_agent, HttpAgent):
      raise TypeError('agent no HttpAgent: ' + http_agent.__class__.__name__)

    self._path = path
    self._data = data

  def _make_scribe_parts(self, scribe):
    return ([scribe.build_part('URL Path', self._path),
             scribe.build_json_part('Payload Data', self._data)]
            + super(HttpPostOperation, self)._make_scribe_parts(scribe))

  def execute(self, agent=None, trace=True):
    if not self.agent:
      if not isinstance(agent, HttpAgent):
        raise TypeError('agent no HttpAgent: ' + agent.__class__.__name__)
      self.bind_agent(agent)

    http_response = agent.post(self._path, self._data, trace=trace)
    status = agent._new_post_status(self, http_response)
    if trace:
      agent.logger.debug('Returning status %s', status)
    return status
