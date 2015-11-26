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


"""Provides base support for TestableAgents based on HTTP interactions."""

import base64
import collections
import httplib
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
    """Implements Scribbable_make_scribe_parts interface."""
    label = 'Response Error' if self.error else 'Response Data'
    data = self.error if self.error else self.output
    return [scribe.build_part('HTTP Code', self.retcode),
            scribe.build_json_part(label, data)]

  def ok(self):
    """Return true if the result code indicates an OK HTTP response."""
    return self.retcode >= 200 and self.retcode < 300

  def check_ok(self):
    """Raise ValueError if the result code does not indicate an OK response."""
    if not self.ok():
      raise ValueError('Unexpected HTTP response {code}:\n{body}'.format(
          code=self.retcode, body=self.error or self.output))


class HttpOperationStatus(testable_agent.AgentOperationStatus):
  """Specialization of AgentOperationStatus for HttpAgent operations.

  This class assumes generic synchronous HTTP requests. Services may
  still wish to refine this further. Especially if they use an additional
  protocol, such as returning references to asynchronous status updates.
  """
  # pylint: disable=missing-docstring
  @property
  def finished(self):
    return True

  @property
  def timed_out(self):
    return self.__http_response.retcode in [httplib.REQUEST_TIMEOUT,
                                            httplib.GATEWAY_TIMEOUT]

  @property
  def finished_ok(self):
    return self.__http_response.ok()

  @property
  def detail(self):
    return self.__http_response.output

  @property
  def error(self):
    return self.__http_response.error

  def __init__(self, operation, http_response):
    super(HttpOperationStatus, self).__init__(operation)
    self.__http_response = http_response

  def __cmp__(self, response):
    return self.__http_response.__cmp__(response.__http_response)

  def __str__(self):
    return 'http_response={0}'.format(self.__http_response)

  def set_http_response(self, http_response):
    self.__http_response = http_response


class SynchronousHttpOperationStatus(HttpOperationStatus):
  """An HttpOperationStatus for a synchronous request.

  Really this just means that there is no need for a request ID
  to track the request later.
  """
  # pylint: disable=missing-docstring
  @property
  def id(self):
    return None

  @property
  def timed_out(self):
    return False


class HttpAgent(testable_agent.TestableAgent):
  """A specialization of TestableAgent for interacting with HTTP services."""

  @property
  def headers(self):
    """Returns the dictionary specifying default headers to send with messages.

    Use add_header() to add additional headers.
    """
    return self.__headers

  @property
  def baseUrl(self):
    """Returns the bound base URL used when sending messages."""
    return self.__base_url

  def __init__(self, base_url):
    """Constructs instance.

    Args:
      base_url: [string] Specifies the base url to this agent's HTTP endpoint.
    """
    super(HttpAgent, self).__init__()
    self.__base_url = base_url
    self.__status_class = HttpOperationStatus
    self.__headers = {}

  def add_header(self, key, value):
    """Specifies a header to add to each request that follows.

    Args:
      key: Header key to add.
      value: Header value to add.
    """
    self.__headers[key] = value

  def add_basic_auth_header(self, user, password):
    """Adds an Authorization header for HTTP Basic Authentication."""
    encoded_auth = base64.encodestring('{user}:{password}'.format(
        user=user, password=password))[:-1]  # strip eoln
    self.add_header('Authorization', 'Basic ' + encoded_auth)

  def _make_scribe_parts(self, scribe):
    """Implements Scribbable_make_scribe_parts interface."""
    return ([scribe.build_part('Base URL', self.__base_url)]
            + super(HttpAgent, self)._make_scribe_parts(scribe))

  def new_post_operation(self, title, path, data, status_class=None):
    """Acts as an AgentOperation factory.

    Args:
      title: See AgentOperation title
      path: The URL path to POST to. The Agent provides the network location.
      data: The HTTP payload to post to the server.

      TODO(ewiseblatt): Will need to add headers.
    """
    return HttpPostOperation(title, path, data, self,
                             status_class=status_class)

  def new_delete_operation(self, title, path, data, status_class=None):
    """Acts as an AgentOperation factory.

    Args:
      title: See AgentOperation title
      path: The URL path to DELETE to. The Agent provides the network location.
      data: The HTTP payload to send to the server with the DELETE.

      TODO(ewiseblatt): Will need to add headers.
    """
    return HttpDeleteOperation(title, path, data, self,
                               status_class=status_class)

  def _new_messaging_status(self, operation, http_response):
    """Acts as an OperationStatus factory for HTTP messaging requests.

    This method is intended to be used internally and by subclasses, not
    by normal callers.

    Args:
      operation: The AgentOperation the status is for.
      http_response: The HttpResponseType from the original HTTP response.
    """
    return self.__status_class(operation, http_response)

  def _send_http_request(self, path, http_type,
                         data=None, headers=None, trace=True):
    """Send an HTTP message.

    Args:
      path: [string] The URL path to send to (without network location)
      http_type: [string] The HTTP message type (e.g. POST)
      data: [string] Data payload to send, if any.
      headers: [dict] Headers to write, if any.
      trace: [bool] True if should log request and response.

    Returns:
      HttpResponseType
    """
    if headers == None:
      all_headers = self.__headers
    else:
      all_headers = self.__headers.copy()
      all_headers.update(headers)

    if path[0] == '/':
      path = path[1:]
    url = '{0}/{1}'.format(self.__base_url, path)

    req = urllib2.Request(url=url, data=data, headers=all_headers)
    req.get_method = lambda: http_type

    if trace:
      self.logger.debug('%s url=%s data=%s', http_type, url, data)

    output = None
    error = None
    try:
      response = urllib2.urlopen(req)
      code = response.getcode()
      output = response.read()
      if trace:
        self.logger.debug('  -> http=%d: %s', code, output)
    except urllib2.HTTPError as ex:
      code = ex.getcode()
      error = ex.read()
      if trace:
        self.logger.debug('  -> http=%d: %s', code, error)
    except urllib2.URLError as ex:
      if trace:
        self.logger.debug('  *** except: %s', ex)
      code = -1
      error = str(ex)
    return HttpResponseType(code, output, error)


  def post(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP POST."""
    return self._send_http_request(
        path, 'POST', data=data,
        headers={'Content-Type': content_type}, trace=trace)

  def delete(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP DELETE."""
    return self._send_http_request(
        path, 'DELETE', data=data,
        headers={'Content-Type': content_type}, trace=trace)

  def get(self, path, trace=True):
    """Perform an HTTP GET."""
    return self._send_http_request(path, 'GET', trace=trace)


class BaseHttpOperation(testable_agent.AgentOperation):
  """Specialization of AgentOperation that performs HTTP POST."""
  @property
  def path(self):
    """The path component of the URL to message to."""
    return self.__path

  @property
  def data(self):
    """The HTTP payload data to send, or None if there is no payload."""
    return self.__data

  @property
  def status_class(self):
    """The class to instantiate for the OperationStatus."""
    return self.__status_class

  def __init__(self, title, path, data,
               http_agent=None, status_class=HttpOperationStatus):
    """Construct a new operation.

    Args:
      title [string]: The name of the operation for reporting purposes.
      path [string]: The URL path to invoke.
      data [string]: If not empty, post this data with the invocation.
      http_agent [HttpAgent]: If provided, invoke with this agent.
      status_class [HttpOperationStatus]: If provided, use this for the
         result status returned by the operation.
    """
    super(BaseHttpOperation, self).__init__(title, http_agent)
    if http_agent and not isinstance(http_agent, HttpAgent):
      raise TypeError('agent no HttpAgent: ' + http_agent.__class__.__name__)

    self.__path = path
    self.__data = data
    self.__status_class = status_class

  def _make_scribe_parts(self, scribe):
    """Implements Scribbable_make_scribe_parts interface."""
    return ([scribe.build_part('URL Path', self.__path),
             scribe.build_json_part('Payload Data', self.__data)]
            + super(BaseHttpOperation, self)._make_scribe_parts(scribe))

  def execute(self, agent=None, trace=True):
    if not self.agent:
      if not isinstance(agent, HttpAgent):
        raise TypeError('agent no HttpAgent: ' + agent.__class__.__name__)
      self.bind_agent(agent)

    status = self._send_message(agent, trace)
    if trace:
      agent.logger.debug('Returning status %s', status)
    return status

  def _send_message(self, agent, trace):
    """Placeholder for specializations to perform actual HTTP messaging."""
    raise NotImplementedError()


class HttpPostOperation(BaseHttpOperation):
  """Specialization of AgentOperation that performs HTTP POST."""
  def _send_message(self, agent, trace):
    """Implements BaseHttpOperation interface."""
    # pylint: disable=protected-access
    http_response = agent.post(self.path, self.data, trace=trace)
    status = agent._new_messaging_status(self, http_response)
    return status


class HttpDeleteOperation(BaseHttpOperation):
  """Specialization of AgentOperation that performs HTTP DELETE."""
  def _send_message(self, agent, trace):
    """Implements BaseHttpOperation interface."""
    # pylint: disable=protected-access
    http_response = agent.delete(self.path, self.data, trace=trace)
    status = agent._new_messaging_status(self, http_response)
    return status
