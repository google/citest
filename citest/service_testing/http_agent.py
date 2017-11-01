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


"""Provides base support for BaseAgents based on HTTP interactions."""

import base64
import collections
import httplib
import json
import traceback
import urllib2

from citest.base import JournalLogger
from citest.base import JsonSnapshotableEntity
from .http_scrubber import HttpScrubber

from . import base_agent


class HttpResponseType(
    collections.namedtuple('HttpResponseType',
                           ['http_code', 'output', 'exception']),
    JsonSnapshotableEntity):
  """Holds the results from an HTTP message.

  Attributes:
    http_code: The HTTP response code (or None if exception attempting to send).
    output: The HTTP response.
    exception: The exception if http_code is None
  """

  @property
  def error_message(self):
    """A string denoting the error this response represents, if any."""
    return (None if self.ok()
            else self.exception if self.exception else self.output)

  def __str__(self):
    return 'http_code={0} output={1!r} exception={2!r}'.format(
        self.http_code, self.output, self.exception)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface.

    The payload will be emitted as a string. Consider calling
    export_to_json_snapshot_with_format instead to specify the payload format.
    """
    self.export_to_json_snapshot_with_format(snapshot, entity, format=None)

  def export_to_json_snapshot_with_format(self, snapshot, entity, format):
    """Helper function for JsonSnapshotableEntity, allowing a format tag.

    Args:
      snapshot: [JsonSnapshot] The snapshot owning the entity.
      entity: [SnapshotEnityt] The snapshot entity to export into.
      format: [string] If specified, add this value as a "format" metadata tag
          for the payload value.
    """
    builder = snapshot.edge_builder
    edge = builder.make(entity, 'HTTP Code', self.http_code)
    if not self.ok():
      edge.add_metadata('relation', 'ERROR')
    if self.exception:
      edge = builder.make_error(entity, 'Response Error', self.exception)
      if format:
        edge.add_metadata('format', format)
    if self.output or not self.exception:
      # If no output on success, explicitly show that.
      edge = builder.make_output(entity, 'Response Output', self.output)
      if format:
        edge.add_metadata('format', format)

  def ok(self):
    """Return true if the result code indicates an OK HTTP response."""
    return self.http_code >= 200 and self.http_code < 300

  def check_ok(self):
    """Raise ValueError if the result code does not indicate an OK response."""
    if not self.ok():
      if self.exception:
        raise ValueError('HTTP has no response: {ex}'.format(ex=self.exception))
      else:
        raise ValueError('Unexpected HTTP response {code}:\n{body}'.format(
            code=self.http_code, body=self.output))


class HttpOperationStatus(base_agent.AgentOperationStatus):
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
    return self.__http_response.http_code in [httplib.REQUEST_TIMEOUT,
                                              httplib.GATEWAY_TIMEOUT]

  @property
  def id(self):
    return str(id(self))

  @property
  def finished_ok(self):
    return self.__http_response.ok()

  @property
  def detail(self):
    return self.__http_response.output

  @property
  def error(self):
    return self.__http_response.error_message

  @property
  def snapshot_format(self):
    return self.__snapshot_format

  @property
  def raw_http_response(self):
    return self.__http_response

  def __init__(self, operation, http_response):
    super(HttpOperationStatus, self).__init__(operation)
    self.__http_response = http_response
    self.__snapshot_format = None

  def __cmp__(self, response):
    return self.__http_response.__cmp__(response.raw_http_response)

  def __str__(self):
    return 'http_response={0}'.format(self.__http_response)

  def set_snapshot_format(self, format):
    """Sets the snapshot format.

    This could be a property setter, but is intended to be called by base
    classes and not really by consumers.
    """
    self.__snapshot_format = format

  def set_http_response(self, http_response):
    self.__http_response = http_response

  def export_to_json_snapshot(self, snapshot, entity):
    super(HttpOperationStatus, self).export_to_json_snapshot(snapshot, entity)
    self.__http_response.export_to_json_snapshot_with_format(
        snapshot, entity, format=self.__snapshot_format)


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


class HttpAgent(base_agent.BaseAgent):
  """A specialization of BaseAgent for interacting with HTTP services."""

  @property
  def headers(self):
    """Returns the dictionary specifying default headers to send with messages.

    Use add_header() to add additional headers.
    """
    return self.__headers

  @property
  def base_url(self):
    """Returns the bound base URL used when sending messages."""
    return self.__base_url

  @property
  def http_scrubber(self):
    """Returns the bound scrubber for scrubbing components of HTTP messages."""
    return self.__http_scrubber

  @http_scrubber.setter
  def http_scrubber(self, scrubber):
    """Binds HttpScrubber for removing private information when logging HTTP."""
    self.__http_scrubber = scrubber

  @staticmethod
  def make_json_payload_from_object(payload_obj):
    """Make an HTTP payload as the JSON form of an object instance.

    Args:
      obj: An object representation of the entire payload.

    Returns:
       JSON encoded payload string.
    """
    return json.JSONEncoder().encode(payload_obj)

  @staticmethod
  def make_json_payload_from_kwargs(**kwargs):
    """Make an HTTP operation JSON payload string from Python objects.

    Args:
       kwargs: [dict] The dictionary defining the payload to send.
          The payload will be the dictionary encoded as json.
    Returns:
       JSON encoded payload string for Gate request.
    """
    payload_dict = kwargs
    return json.JSONEncoder().encode(payload_dict)

  def __init__(self, base_url):
    """Constructs instance.

    Args:
      base_url: [string] Specifies the base url to this agent's HTTP endpoint.
    """
    super(HttpAgent, self).__init__()
    self.__base_url = base_url
    self.__status_class = HttpOperationStatus
    self.__headers = {}
    self.__http_scrubber = HttpScrubber()

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

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Base URL', self.__base_url)
    super(HttpAgent, self).export_to_json_snapshot(snapshot, entity)

  def new_post_operation(self, title, path, data, status_class=None,
                         max_wait_secs=None):
    """Acts as an AgentOperation factory.

    Args:
      title: See AgentOperation title
      path: The URL path to POST to. The Agent provides the network location.
      data: The HTTP payload to post to the server.
      max_wait_secs: [float] Max number of seconds to wait for status
          completion. None indicates unlimited.

      TODO(ewiseblatt): Will need to add headers.
    """
    return HttpPostOperation(title, path, data, self,
                             status_class=status_class,
                             max_wait_secs=max_wait_secs)

  def new_delete_operation(self, title, path, data, status_class=None,
                           max_wait_secs=None):
    """Acts as an AgentOperation factory.

    Args:
      title: See AgentOperation title
      path: The URL path to DELETE to. The Agent provides the network location.
      data: The HTTP payload to send to the server with the DELETE.
      max_wait_secs: [float] Max number of seconds to wait for status
          completion. None indicates unlimited.

      TODO(ewiseblatt): Will need to add headers.
    """
    return HttpDeleteOperation(title, path, data, self,
                               status_class=status_class,
                               max_wait_secs=max_wait_secs)

  def _new_messaging_status(self, operation, http_response):
    """Acts as an OperationStatus factory for HTTP messaging requests.

    This method is intended to be used internally and by subclasses, not
    by normal callers.

    Args:
      operation: The AgentOperation the status is for.
      http_response: The HttpResponseType from the original HTTP response.
    """
    status_class = operation.status_class or self.__status_class
    return status_class(operation, http_response)

  def __send_http_request(self, path, http_type,
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
    if headers is None:
      all_headers = self.__headers
    else:
      all_headers = self.__headers.copy()
      all_headers.update(headers)

    if path[0] == '/':
      path = path[1:]
    url = '{0}/{1}'.format(self.__base_url, path)

    req = urllib2.Request(url=url, data=data, headers=all_headers)
    req.get_method = lambda: http_type

    scrubbed_url = self.__http_scrubber.scrub_url(url)
    scrubbed_data = self.__http_scrubber.scrub_request(data)

    if data is not None:
      JournalLogger.journal_or_log_detail(
          '{type} {url}'.format(type=http_type, url=scrubbed_url),
          scrubbed_data,
          _module=self.logger.name, _alwayslog=trace,
          _context='request')
    else:
      JournalLogger.journal_or_log(
          '{type} {url}'.format(type=http_type, url=scrubbed_url),
          _module=self.logger.name, _alwayslog=trace, _context='request')

    code = None
    output = None
    exception = None
    try:
      response = urllib2.urlopen(req)
      code = response.getcode()
      output = response.read()

      scrubbed_output = self.__http_scrubber.scrub_response(output)
      JournalLogger.journal_or_log_detail(
          'HTTP {code}'.format(code=code),
          scrubbed_output,
          _module=self.logger.name, _alwayslog=trace, _context='response')

    except urllib2.HTTPError as ex:
      code = ex.getcode()
      output = ex.read()
      scrubbed_error = self.__http_scrubber.scrub_response(output)
      JournalLogger.journal_or_log_detail(
          'HTTP {code}'.format(code=code), scrubbed_error,
          _module=self.logger.name, _alwayslog=trace, _context='response')

    except urllib2.URLError as ex:
      JournalLogger.journal_or_log(
          'Caught exception: {ex}\n{stack}'.format(
              ex=ex, stack=traceback.format_exc()))
      exception = ex
    return HttpResponseType(code, output, exception)

  def patch(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP PATCH."""
    return self.__send_http_request(
        path, 'PATCH', data=data,
        headers={'Content-Type': content_type}, trace=trace)

  def post(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP POST."""
    return self.__send_http_request(
        path, 'POST', data=data,
        headers={'Content-Type': content_type}, trace=trace)

  def put(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP PUT."""
    return self.__send_http_request(
        path, 'PUT', data=data,
        headers={'Content-Type': content_type}, trace=trace)

  def delete(self, path, data, content_type='application/json', trace=True):
    """Perform an HTTP DELETE."""
    return self.__send_http_request(
        path, 'DELETE', data=data,
        headers={'Content-Type': content_type}, trace=trace)

  def get(self, path, trace=True):
    """Perform an HTTP GET."""
    return self.__send_http_request(path, 'GET', trace=trace)


class BaseHttpOperation(base_agent.AgentOperation):
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
    """The overriden class to instantiate for the OperationStatus.

    If this returns None then use the agent's default class.
    """
    return self.__status_class

  def __init__(self, title, path, data,
               http_agent=None, status_class=None, max_wait_secs=None):
    """Construct a new operation.

    Args:
      title [string]: The name of the operation for reporting purposes.
      path [string]: The URL path to invoke.
      data [string]: If not empty, post this data with the invocation.
      http_agent [HttpAgent]: If provided, invoke with this agent.
      status_class [HttpOperationStatus]: If provided, use this for the
         result status returned by the operation. Otherwise it will use
         the agent's default.
      max_wait_secs: [float] Max number of seconds to wait for status
          completion. None indicates unlimited.
    """
    super(BaseHttpOperation, self).__init__(title, http_agent,
                                            max_wait_secs=max_wait_secs)
    if http_agent and not isinstance(http_agent, HttpAgent):
      raise TypeError('agent no HttpAgent: ' + http_agent.__class__.__name__)

    self.__path = path
    self.__data = data
    self.__status_class = status_class
    self.__snapshot_format = None

  def set_snapshot_format(self, format):
    """Sets 'format' metadata value to specify when snapshotting operation."""
    self.__snapshot_format = format

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'URL Path', self.__path)
    edge = snapshot.edge_builder.make_data(entity, 'Payload Data', self.__data)
    if self.__snapshot_format:
      edge.add_metadata('format', self.__snapshot_format)
    super(BaseHttpOperation, self).export_to_json_snapshot(snapshot, entity)

  def execute(self, agent=None):
    if not self.agent:
      if not isinstance(agent, HttpAgent):
        raise TypeError('agent no HttpAgent: ' + agent.__class__.__name__)
      self.bind_agent(agent)

    status = self._send_message(agent, trace=True)
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


class HttpPutOperation(BaseHttpOperation):
  """Specialization of AgentOperation that performs HTTP PUT."""
  def _send_message(self, agent, trace):
    """Implements BaseHttpOperation interface."""
    # pylint: disable=protected-access
    http_response = agent.put(self.path, self.data, trace=trace)
    status = agent._new_messaging_status(self, http_response)
    return status

class HttpPatchOperation(BaseHttpOperation):
  """Specialization of AgentOperation that performs HTTP PATCH."""
  def _send_message(self, agent, trace):
    """Implements BaseHttpOperation interface."""
    # pylint: disable=protected-access
    http_response = agent.patch(self.path, self.data, trace=trace)
    status = agent._new_messaging_status(self, http_response)
    return status
