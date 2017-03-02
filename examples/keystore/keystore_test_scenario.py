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


"""Acts as a common base class for the different tests cases on the keystore.

For simple tests such as these, you might not need a base class. However for
purposes of illustration, we showing how to write synchronous tests and
asynchronous tests and keeping these separate. Each of these has some common
functionality, such as wanting to fork (and terminate) the keystore server.
We'll put that here in this class.

Note that we are doing this in the AgentTestCase. We could use the scenario
to do this. Especially if we wanted to use different TestCase classes on the
same running server.

Note also that non-trivial systems are likely to have their lifecycle
management outside the scope of these test classes. In otherwords, tests
do not fork and tear down servers in general. Doing so here makes for a simple
hermetic test for purposes of illustration and convienence since we can.
"""

import logging
import os
import signal
import socket
import subprocess
import time

from citest.service_testing import AgentTestScenario
from citest.service_testing import HttpAgent


class KeystoreTestScenario(AgentTestScenario):
  """Provides global and shared state among tests on the Keystore.

  What to put in the scenario vs in the test case is subjective,
  however the scenario contains the variable bindings for the tests
  and acts as the primary agent factory for agent operations.

  In our tests, we're going to use the same agent for both operations and
  observations. This doesnt affect anything about the scenario other than
  we might have created an observation agent here.

  We're going to have our tests automatically fork a server since it is
  trivial. In general the server may require an additional deployment process
  that would live outside the scope of these tests and be assumed already
  deployed before running the test.

  We'll fork the server when the scenario is constructed. We'll add an
  explicit cleanup call to the scenario which will terminate the server.
  We will require that our test harness call the cleanup.
  """

  @classmethod
  def init_bindings_builder(cls, builder, defaults=None):
    """Implements citest.service_testing.AgentTestScenario.init_bindings_builder.
    This scenario introduces command-line parameters to specify and override
    where the keystore server is located from the command-line.
    """
    super(KeystoreTestScenario, cls).init_bindings_builder(
        builder, defaults=defaults)
    defaults = defaults or {}
    builder.add_argument('--host', default=defaults.get('HOST', 'localhost'),
                         help='The host to locate the server at.')
    builder.add_argument('--port', default=defaults.get('PORT', 0),
                         type=int,
                         help='The port to use. If None then pick one.')

  def __init__(self, bindings):
    """Construct the scenario.

    When constructing the scenario, this may fork a server if the bindings
    indicate using port 0 on localhost. In that case, a port will be picked
    and written into the bindings, and a server forked using that port.

    The instance should be cleaned up by calling cleanup.
    """
    super(KeystoreTestScenario, self).__init__(bindings)

    self.__server = None
    port = bindings['PORT']
    if port == 0:
      host = bindings['HOST']
      if host != 'localhost' and host != '127.0.0.1':
        raise ValueError('Must either specify a --port or be on --localhost.')
      bindings['PORT'] = KeystoreTestScenario.__pick_unused_port()
      self.__server = self.__fork_server(bindings['PORT'])

  def new_agent(self, bindings):
    """Implements citest.service_testing.AgentTestScenario.new_agent."""
    return HttpAgent('http://{host}:{port}'.format(
        host=bindings['HOST'], port=bindings['PORT']))

  def cleanup(self):
    """Cleanup the scenario."""
    if self.__server is not None:
      logging.getLogger(__name__).info('Killing server.')
      os.killpg(os.getpgid(self.__server.pid), signal.SIGTERM)
      self.__server = None

  def make_key(self, name):
    """Helper function that creates keys specific to this invocation."""
    return name + self.bindings['TEST_ID']

  def __fork_server(self, port):
    """Forks a server using the specified port.

    Args:
       port: [int] The port the server should listen on.

    Returns:
       The popen'd process that should be passed back into to kill_server.
    """
    wait_until_ready = True

    log = logging.getLogger(__name__)
    log.info('Forking keystore_server on port %d', port)
    server = subprocess.Popen(
        ' '.join(['python',
                  os.path.join(os.path.abspath(os.path.dirname(__file__)),
                               'keystore_server.py'),
                  '--port', str(port), '>&/dev/null']),
        preexec_fn=os.setsid,
        shell=True)

    # Wait for server to become ready
    if wait_until_ready:
      log.info('Waiting for server on port %d...', port)

      while True:
        try:
          sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
          sock.connect(('localhost', port))
          sock.close()
          break
        except IOError:
          time.sleep(0.01)
      log.info('Server is ready.')

    return server

  @staticmethod
  def __pick_unused_port():
    """Retursn a port number not currently in use.

    Note that the port returned may become used once it is returned,
    either by the caller or anyone else. This isnt guaranteed at time of use.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('localhost', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port
