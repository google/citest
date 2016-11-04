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

# pylint: disable=invalid-name
# pylint: disable=missing-docstring
# pylint: disable=unused-variable

import argparse
import json
import sys
import threading
import time

import BaseHTTPServer


class ThreadSafeDict(object):
  # pylint: disable=too-few-public-methods
  def __init__(self):
    self.__lock = threading.Lock()
    self.__data = {}

  def add_unique(self, value):
    with self.__lock:
      key = 'task-' + str(len(self.__data) + 1)
      self.__data[key] = value
    return key

  def __setitem__(self, key, item):
    with self.__lock:
      self.__data[key] = item

  def __getitem__(self, key):
    with self.__lock:
      return self.__data[key]

  def __delitem__(self, key):
    with self.__lock:
      del self.__data[key]

  def __len__(self):
    with self.__lock:
      return len(self.__data)



_tasks = ThreadSafeDict()

class AsyncTask(object):
  @staticmethod
  def find_status(identifier):
    return _tasks[identifier].__status

  @staticmethod
  def enqueue(operation, delay):
    task = AsyncTask(operation, float(str(delay)))
    thread = threading.Thread(target=task)
    print 'STARTING TASK ' + str(task)
    thread.start()
    return task

  @property
  def identifier(self):
    return self.__id

  def __init__(self, operation, delay):
    self.__operation = operation
    self.__status = 'WAITING'
    self.__delay = delay
    self.__id = _tasks.add_unique(self)

  def __call__(self):
    try:
      self.__status = 'RUNNING'
      time.sleep(self.__delay)
      self.__operation()
      self.__status = 'DONE'
    except BaseException as bex:
      print 'CAUGHT {0!r}'.format(bex)
      self.__status = 'ERROR {0} {1}'.format(
          bex.__class__.__name__, bex.message)


_key_store = ThreadSafeDict()


class SimpleRequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):
  def decode_request(self, request):
    parameters = {}
    path, ignore, query = request.partition('?')
    if not query:
      return request, parameters, None
    query, ignore, fragment = query.partition('#')

    for part in query.split('&'):
      key, ignore, value = part.partition('=')
      parameters[key] = value

    return path, parameters, fragment

  def do_HEAD(self):
    self.send_response(200, {'Content-Type': 'text/html'})

  def do_DELETE(self):
    path, parameters, fragment = self.decode_request(self.path)
    code = 404
    headers = {}
    body = 'Not Found: path={0}'.format(path)
    key = path[1:].split('/', 1)[1]

    if path.startswith('/delete/'):
      code, headers, body = self.__do_delete(key, parameters)

    self.send_response(code)
    for key, value in headers.items():
      self.send_header(key, value)
    self.end_headers()
    self.wfile.write(body)

  def do_POST(self):
    path, parameters, fragment = self.decode_request(self.path)
    code = 404
    headers = {}
    body = 'Not Found: path={0}'.format(path)

    key = path[1:].split('/', 1)[1]
    if path.startswith('/put/'):
      code, headers, body = self.__do_put(key, parameters)
    elif path.startswith('/put_random/'):
      code, headers, body = self.__do_put_random(key, parameters)

    self.send_response(code)
    for key, value in headers.items():
      self.send_header(key, value)
    self.end_headers()
    self.wfile.write(body)

  def do_GET(self):
    request = self.request
    path, parameters, fragment = self.decode_request(self.path)

    code = 404
    headers = {}
    body = 'Not Found: path={0}'.format(path)

    if path.startswith('/lookup/'):
      code, headers, body = self.__do_lookup(path[1:].split('/', 1)[1])
    elif path.startswith('/status/'):
      code, headers, body = self.__do_status(path[1:].split('/', 1)[1])
    elif path == '/exit':
      code, body = 200, 'BYE'

    self.send_response(code)
    for key, value in headers.items():
      self.send_header(key, value)
    self.end_headers()
    self.wfile.write(body)

    if path == '/exit':
      sys.exit(0)

  def __do_put(self, key, parameters):
    content = self.rfile.read(int(self.headers['Content-Length']))
    value = json.JSONDecoder().decode(content)

    if 'async' in parameters:
      def fn():
        _key_store[key] = value
      task = AsyncTask.enqueue(fn, parameters.get('delay', 1.5))
      return 200, {}, task.identifier

    _key_store[key] = value
    return 200, {}, 'OK'

  def __do_put_random(self, key, parameters):
    value = 'Random Value "{0}"'.format(time.time())
    if 'async' in parameters:
      def fn():
        _key_store[key] = value
      task = AsyncTask.enqueue(fn, parameters.get('delay', 1.5))
      return 200, {}, task.identifier

    _key_store[key] = value
    return 200, {}, value

  def __do_delete(self, key, parameters):
    if 'async' in parameters:
      def fn():
        del _key_store[key]
      task = AsyncTask.enqueue(fn, parameters.get('delay', 1.5))
      return 200, {}, task.identifier

    try:
      result = json.JSONEncoder().encode({key: _key_store[key]})
      del _key_store[key]
      return 200, {}, result
    except KeyError:
      return 404, {}, 'Key "{0}" not found.'.format(key)

  def __do_status(self, key):
    try:
      value = AsyncTask.find_status(key)
      return 200, {}, value
    except KeyError:
      return 404, {}, 'Task \"{0}\" Not Found'.format(key)

  def __do_lookup(self, key):
    try:
      value = _key_store[key]
      doc = json.JSONEncoder().encode(value)
      return 200, {'ContentType': 'application/json'}, doc
    except KeyError:
      return 404, {}, 'Key \"{0}\" Not Found'.format(key)


def main():
  parser = argparse.ArgumentParser()
  parser.add_argument('--port', default=8712, type=int)
  options = parser.parse_args()

  httpd = BaseHTTPServer.HTTPServer(('localhost', options.port),
                                    SimpleRequestHandler)
  httpd.serve_forever()


if __name__ == '__main__':
  main()
