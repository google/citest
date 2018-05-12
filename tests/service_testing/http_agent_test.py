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
# pylint: disable=invalid-name

"""Test HttpAgent"""


import BaseHTTPServer
import logging
import socket
import threading
import urllib2

import unittest

from citest.base import ExecutionContext
from citest.json_contract import (
    ObservationPredicateFactory,
    ObservationValuePredicate)
from citest.service_testing import (
    HttpAgent,
    HttpContractBuilder,
    HttpOperationStatus,
    HttpResponseObserver,
    HttpResponsePredicate,
    HttpAgentErrorPredicate,
    HttpResponseType)

ov_factory = ObservationPredicateFactory()


class TestAsyncStatus(HttpOperationStatus):
  @property
  def finished(self):
    return self.__final_code != None

  @property
  def finished_ok(self):
    return self.__final_code is not None and self.__final_code < 300

  @property
  def error(self):
    return self.__final_code is not None and self.__final_code >= 400

  def refresh(self):
    self.__refresh_calls += 1
    if self.__refresh_calls < self.__refresh_threshold:
      return
    self.__final_code = self.__defer_code
    self.set_http_response(HttpResponseType(http_code=self.__final_code))

  def __init__(self, final_code, refresh_threshold,
               operation, original_response=None):
    super(TestAsyncStatus, self).__init__(operation, original_response)
    self.__defer_code = final_code
    self.__refresh_threshold = refresh_threshold
    self.__final_code = None
    self.__refresh_calls = 0


class TestAsyncStatusFactory(object):
  """Helper class to inject desired asynchronous response into normal status.

  This is used by the Operation when testing with an async Status.
  The Operation API calls this factory with its interface via the __call__
  method. Then this instance will create a TestAsyncStatus that is configured
  to return a particular code after a certain number of wait calls as determined
  by the test creating this factory instance.
  """

  # pylint: disable=too-few-public-methods
  def __init__(self, final_code, refresh_threshold):
    self.__final_code = final_code
    self.__refresh_threshold = refresh_threshold

  def __call__(self, *posargs, **kwargs):
    return TestAsyncStatus(self.__final_code, self.__refresh_threshold,
                           *posargs, **kwargs)


class TestServer(BaseHTTPServer.BaseHTTPRequestHandler):
  @staticmethod
  def make(port):
    logging.info('Starting TestServer on port=%d', port)
    return BaseHTTPServer.HTTPServer(('localhost', port), TestServer)

  def respond(self, code, headers, body=None):
    """Send response to the HTTP request."""
    self.send_response(code)
    for key, value in headers.items():
      self.send_header(key, value)
    self.end_headers()
    if body:
      self.wfile.write(body)

  def decode_request(self, request):
    """Extract the URL components from the request."""
    parameters = {}
    path, _, query = request.partition('?')
    if not query:
      return request, parameters, None
    query, _, fragment = query.partition('#')

    for part in query.split('&'):
      key, _, value = part.partition('=')
      parameters[key] = value

    return path, parameters, fragment or None

  def do_GET(self):
    _, parameters, _ = self.decode_request(self.path)
    response_code = int(parameters.get('code', 200))
    response_message = parameters.get('message', '')
    content_type = parameters.get('type', 'text/html')
    self.respond(
        response_code,
        {'Content-Type': content_type, 'XCall': 'GET'},
        response_message)

  def do_POST(self):
    _, parameters, _ = self.decode_request(self.path)
    response_code = int(parameters.get('code', 200))
    num_bytes = int(self.headers.getheader('content-length', 0))
    response_message = self.rfile.read(num_bytes)
    content_type = parameters.get('type', 'text/html')
    self.respond(
        response_code,
        {'Content-Type': content_type, 'XCall': 'POST'},
        response_message)

  def do_DELETE(self):
    _, parameters, _ = self.decode_request(self.path)
    response_code = int(parameters.get('code', 200))
    num_bytes = int(self.headers.getheader('content-length', 0))
    response_message = self.rfile.read(num_bytes)
    content_type = parameters.get('type', 'text/html')
    self.respond(
        response_code,
        {'Content-Type': content_type, 'XCall': 'DELETE'},
        response_message)


def headers_to_dict(header_list):
  if header_list is None:
    return None

  result = {}
  for entry in header_list:
    key, value = entry.split(':', 1)
    result[key] = value.strip()
  return result


class HttpAgentTest(unittest.TestCase):
  PORT = None
  SERVER = None

  @staticmethod
  def __alloc_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return int(port)

  @staticmethod
  def setUpClass():
    HttpAgentTest.PORT = HttpAgentTest.__alloc_port()
    HttpAgentTest.SERVER = TestServer.make(HttpAgentTest.PORT)
    server_thread = threading.Thread(
        target=HttpAgentTest.SERVER.serve_forever,
        name='server')
    server_thread.daemon = True
    server_thread.start()

  def setUp(self):
    self.agent = HttpAgent('http://localhost:%d' % HttpAgentTest.PORT)
    self.context = ExecutionContext()
    
  def test_http_get(self):
    response = self.agent.get('test')
    self.assertEquals(200, response.http_code)
    self.assertEquals('', response.output)
    self.assertIsNone(response.exception)

    tests = [(200, 'OK'),
             (201, 'StillOk'),
             (400, 'Dang'),
             (404, 'Whoops'),
             (500, 'Yikes')]
    for code, msg in tests:
      response = self.agent.get('test?code=%d&message=%s' % (code, msg))
      self.assertEquals(code, response.http_code)
      self.assertEquals(msg, response.output)
      if code < 300:
        # urllib2 strips out headers from errors
        self.assertEquals(
            'GET', headers_to_dict(response.headers).get('XCall'))

  def test_http_delete(self):
    response = self.agent.get('test')
    self.assertEquals(200, response.http_code)
    self.assertEquals('', response.output)
    self.assertIsNone(response.exception)

    tests = [(200, 'OK'),
             (201, 'StillOk'),
             (400, 'Dang'),
             (404, 'Whoops'),
             (500, 'Yikes')]
    for code, msg in tests:
      response = self.agent.delete('test?code=%d' % code, msg)
      self.assertEquals(code, response.http_code)
      self.assertEquals(msg, response.output)
      if code < 300:
        # urllib2 strips out headers from errors
        self.assertEquals(
            'DELETE', headers_to_dict(response.headers).get('XCall'))

  def test_http_post(self):
    tests = [(200, 'OK'),
             (201, 'StillOk'),
             (400, 'Dang'),
             (404, 'Whoops'),
             (500, 'Yikes')]
    for code, payload in tests:
      response = self.agent.post('test?code=%d' % code, payload)
      self.assertEquals(code, response.http_code)
      self.assertEquals(payload, response.output)
      if code < 300:
        # urllib2 strips out headers from errors
        self.assertEquals(
            'POST', headers_to_dict(response.headers).get('XCall'))

  def test_exception(self):
    self.agent = HttpAgent('http://localhost:%d' % (HttpAgentTest.PORT+1))
    response = self.agent.get('test')
    self.assertIsNone(response.http_code)
    self.assertIsNone(response.output)
    self.assertIsNotNone(response.exception)
    self.assertTrue(isinstance(response.exception, urllib2.URLError))

  def test_post_operation_ok(self):
    op = self.agent.new_post_operation(
        'TestPostOk', 'test/path?code=201', 'Test Data')
    status = op.execute(self.agent)
    self.assertTrue(status.finished)
    self.assertTrue(status.finished_ok)
    self.assertFalse(status.timed_out)
    self.assertEquals('Test Data', status.detail)
    self.assertIsNone(status.error)
    raw_response = status.raw_http_response
    self.assertEquals(201, raw_response.http_code)

  def test_post_operation_bad(self):
    op = self.agent.new_post_operation(
        'TestPostError', 'test/path?code=403', 'Test Error')
    status = op.execute(self.agent)
    self.assertTrue(status.finished)
    self.assertFalse(status.finished_ok)
    self.assertFalse(status.timed_out)
    self.assertEquals('Test Error', status.detail)
    self.assertEquals('Test Error', status.error)

    raw_response = status.raw_http_response
    self.assertEquals(403, raw_response.http_code)
    

  def test_post_operation_timeout(self):
    # A response code of HTTP 408 indicates a timeout
    op = self.agent.new_post_operation(
        'TestPostError', 'test/path?code=408', 'Test Error')
    status = op.execute(self.agent)
    self.assertTrue(status.finished)
    self.assertFalse(status.finished_ok)
    self.assertTrue(status.timed_out)
    self.assertEquals('Test Error', status.detail)
    self.assertEquals('Test Error', status.error)

    raw_response = status.raw_http_response
    self.assertEquals(408, raw_response.http_code)

  def test_post_operation_async_ok(self):
    op = self.agent.new_post_operation(
        'TestAsync', 'test/path?code=201', 'Test Response Line',
        status_class=TestAsyncStatusFactory(208, 1))

    status = op.execute(self.agent)
    self.assertFalse(status.finished)
    self.assertFalse(status.finished_ok)
    status.wait()
    self.assertTrue(status.finished)
    self.assertTrue(status.finished_ok)
    self.assertFalse(status.timed_out)
    self.assertEquals(208, status.raw_http_response.http_code)

  def test_post_operation_async_timeout(self):
    op = self.agent.new_post_operation(
        'TestAsync', 'test/path?code=201', 'Test Response Line',
        status_class=TestAsyncStatusFactory(408, 1))

    status = op.execute(self.agent)
    self.assertFalse(status.finished)
    self.assertFalse(status.finished_ok)
    status.wait()
    self.assertTrue(status.finished)
    self.assertFalse(status.finished_ok)
    self.assertTrue(status.timed_out)
    self.assertEquals(408, status.raw_http_response.http_code)

  def test_contract_ok(self):
    builder = HttpContractBuilder(self.agent)

    # Here we're setting the observer_factory to make an HttpResponseObserver
    # so that the observation objects are the HttpResponseType instance rather
    # than the normal HttpObjectObserver where the objects are the payload data.
    (builder.new_clause_builder('Expect OK')
     .get_url_path('testpath?code=202', observer_factory=HttpResponseObserver)
     .EXPECT(ov_factory.value_list_contains(HttpResponsePredicate(http_code=202))))
    contract = builder.build()
    results = contract.verify(self.context)
    self.assertTrue(results)
    
  def test_contract_failure_ok(self):
    builder = HttpContractBuilder(self.agent)

    # Here we're setting the observer_factory to make an HttpResponseObserver
    # so that the observation objects are the HttpResponseType instance rather
    # than the normal HttpObjectObserver where the objects are the payload data.
    #
    # When we encounter the HTTP error, the HttpResponseType is wrapped in an
    # HttpAgentError object and put into the observation error list.
    # So we need to dig it back out of there.
    # In addition, we're using error_list_matches rather than error_list_contains
    # so we can strict=True to show exactly the one error. "matches" takes a list
    # of predicates, so we wrap the error check into a list.
    (builder.new_clause_builder('Expect NotFound')
     .get_url_path('testpath?code=404', observer_factory=HttpResponseObserver)
     .EXPECT(ov_factory.error_list_matches(
          [HttpAgentErrorPredicate(HttpResponsePredicate(http_code=404))],
          strict=True)))  # Only the one error in the list
    contract = builder.build()
    results = contract.verify(self.context)
    self.assertTrue(results)
    

if __name__ == '__main__':
  logging.basicConfig(
      format='%(levelname).1s %(asctime)s.%(msecs)03d %(message)s',
      datefmt='%H:%M:%S',
      level=logging.DEBUG)

  unittest.main()
