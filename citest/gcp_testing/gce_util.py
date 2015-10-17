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


""" Provides capabilities for establishing connectivity with a GCE instance.

Connectivity can be provided even if it requires tunneling through ssh
because instances are not necessarily exposed through the GCE firewall
for external access.
"""


import atexit
import json
import logging
import os
import socket
import sys
import time
import urllib2


def _unused_port():
  s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  s.bind(('localhost', 0))
  addr, port = s.getsockname()
  s.close()
  return port


class _ProcessKiller(object):
  """Helper class for killing firewall tunnels."""

  def  __init__(self, process):
    self._process = process
  def safe_kill(self):
    try:
      print '*** terminating tunnel'
      os.kill(_process, -9)
    except:
      pass


def _find_internal_ip_interface(iface_list):
  """Find an IP address that is internal from GCE.

  Args:
    iface_list: a list of GCE networkInterface.

  Returns:
    IP address string or None.
  """
  logger = logging.getLogger(__name__)
  for iface in iface_list:
    try:
      ip = iface['networkIP']
      if ip != '127.0.0.1':
        return ip
    except:
      logger.warning('Network Interface has no "networkIP": %s', iface)

  logger.warning('Could not find internal IP interface in %s:', iface_list)
  return None


def _find_external_ip_interface(iface_list):
  """Find an IP address that is external from GCE.

  Args:
    iface_list: a list of GCE networkInterface.

  Returns:
    IP address string or None.
  """
  logger = logging.getLogger(__name__)
  for iface in iface_list:
    try:
      accessConfigs = iface['accessConfigs']
    except:
      logger.error(
          'Description lacks networkInterfaces/accessConfigs field:%s',
          gcloud_response)
      continue
    # Find an external IP address in this list
    for config in accessConfigs:
      try:
        if config['name'] == 'external-nat':
          return config['natIP']
      except:
        logger.warning('Config lacks name or natIP:%s', config)

  logger.warning('Could not find external IP interface in %s:', iface_list)
  return None


def determine_where_i_am():
  """Determine the project/zone/instance this process is running on.

  Returns:
    project, zone, instance  string-triple.
    Each will be None if we are not running on GCE.
  """
  logger = logging.getLogger(__name__)
  headers = { 'Metadata-Flavor': 'Google' }

  url = 'http://metadata/computeMetadata/v1/project/project-id'
  try:
    my_project = urllib2.urlopen(urllib2.Request(url, headers=headers)).read()
  except Exception as e:
    # Likely we are not running on GCE at all.
    logger.debug('We are not running on GCE.' + str(e))
    return None, None, None

  # Since the above succeeded, we expect this to succeed
  url = 'http://metadata/computeMetadata/v1/instance/zone'
  formal_zone = urllib2.urlopen(urllib2.Request(url, headers=headers)).read()
  my_zone = formal_zone.split('/')[-1]
  url = 'http://metadata/computeMetadata/v1/instance/hostname'
  hostname = urllib2.urlopen(urllib2.Request(url, headers=headers)).read()
  my_instance = hostname.split('.')[0]
  logger.debug('We are are running in project=%s zone=%s instance=%s',
               my_project, my_zone, my_instance)
  return my_project, my_zone, my_instance


def am_i(project, zone, instance):
  """Determine if this process is running in the specified instance.

  Args:
    project: A GCP project.
    zone: A GCP zone.
    instance: A GCE instance name.

  Returns:
    True if this process is being run in the specified instance, false otherwise
        including not on GCP at all.
  """
  my_project, my_zone, my_instance = determine_where_i_am()
  if instance != my_instance or my_zone != zone:
    return False
  return not project or project == my_project


def establish_network_connectivity(gcloud, instance, target_port):
  """Determine conventional host:port url for a target_port on an GCE instance.

  GCE instances are firewalled within GCE by default so reaching them may
  require tunneling if this function is called from outside the GCE project.
  If we need to tunnel, the tunnel will be established and remain active
  until exit. To avoid port conflicts, we'll pick an unused local port for
  the tunnel.

  Args:
    gcloud: A GCloudHelper bound to the instance's project and zone.
    instance: The GCE instance name we want to reach.
    target_port: The port number on the instance we are interested in.

  Returns:
    IP host:port address string to the specified GCE instance.
    The port may be different from the target_port if we needed to tunnel
    because it will be on the client-side port of the tunnel (on localhost).
  """
  logger = logging.getLogger(__name__)
  # We're going to use the generic gcloud interface, which will
  # work whether or not we are running in a GCE instance ourselves.

  logger.debug('Testing locating test project instance=%s', instance)
  gcloud_response = gcloud.describe_resource('instances', instance)
  if gcloud_response.retcode != 0:
    logger.error(
        'Could not find instance=%s in project=%s, zone=%s: %s',
        instance, gcloud.project, gcloud.zone, gcloud_response.error)
    return None

  decoder = json.JSONDecoder()
  try:
    doc = decoder.decode(gcloud_response.output)
  except:
    logger.error('Invalid JSON in response: %s', gcloud_response)
    return None

  try:
    if doc['status'] != 'RUNNING':
      logger.error(
          'instance=%s project=%s zone=%s is not RUNNING: %s',
          instance, gcloud.project, gcloud.zone, doc['status'])
      return None
  except:
    logger.warning('Could not check VM status:%s', gcloud_response)

  my_project, my_zone, my_instance = determine_where_i_am()
  if (instance == my_instance
      and gcloud.zone == my_zone
      and (not gcloud.project or my_project == gcloud.project)):
    address = 'localhost:{0}'.format(target_port)
    url = 'http://' + address
    try:
      response = urllib2.urlopen(url, None, 5)
      logger.debug('Running on %s.', url)
      return address
    except IOError:
      logger.error(
        'We are expecting localhost, but %s is not reachable.\n'
        'Maybe it is not running.', url)
      return None

  try:
    iface_list = doc['networkInterfaces']
  except KeyError:
    logger.error('JSON has no networkInterfaces: %s', doc)
    return None

  tried_urls = []
  for which in ['external', 'internal']:
    if which == 'external':
      ip = _find_external_ip_interface(iface_list)
    else:
      ip = _find_internal_ip_interface(iface_list)
    if not ip:
      continue

    logger.debug('%s is on ip=%s', instance, ip)
    url='http://{host}:{port}'.format(host=ip, port=target_port)
    tried_urls.append(url)
    try:
      response = urllib2.urlopen(url, None, 5)
      logger.debug('%s is directly reachable already.', url)
      return '{0}:{1}'.format(ip, target_port)
    except urllib2.URLError:
      pass

  if my_project and (my_project == gcloud.project or not gcloud.project):
    logger.error(
      'We are in the same project %s but cannot reach the server %s.'
      ' It must not be running on port %d, or is bound to localhost',
      my_project, instance, target_port)

  local_port = _unused_port()
  # The use of 'localhost' here will be relative to the instance we ssh into
  # (i.e. it is 'localhost' on the GCE instance, not the client process).
  # GCloud wont need the actual IP address.
  # Since we have the tunnel, we'll be returning 'localhost' with our new port.
  tunnel_spec = '{local_port}:localhost:{target_port}'.format(
    local_port=local_port, target_port=target_port)

  logger.debug(
      'None of %s were directly reachable;\nEstablishing tunnel as %s',
      tried_urls, tunnel_spec)
  logger.info(
      'Could not connect directly. Try tunneling as %s...', tunnel_spec)
  pid, fd = gcloud.pty_fork_ssh(
      instance, ['--ssh-flag="-L %s"' % tunnel_spec], async=True)

  running = False
  try:
    running = not os.kill(pid, 0)
  except OSError:
    pass

  if running:
    print '*** opened tunnel as pid={pid}. This should close at exit.'.format(
        pid=pid)
    atexit.register(_ProcessKiller(pid).safe_kill)

  logger.debug('Confirming tunnel is working')
  url = 'http://localhost:%d' % local_port
  for i in range(5):
    try:
      response = urllib2.urlopen(url, None, 10)
      logger.debug('Confirmed availability (%d)', response.getcode())
      return 'localhost:%d' % local_port
    except:
      time.sleep(1)  # wait a bit longer

  logger.error('Could not connect to our own tunnel at %s', url)
  logger.error('Could not establish connection to %s.', instance)

  return None
