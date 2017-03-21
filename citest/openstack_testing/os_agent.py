# Copyright 2017 Veritas Technologies, LLC. All Rights Reserved.
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


"""Adapts citest CliAgent to ineract with OpenStack."""


# Standard python modules.
import json
import logging

# Our modules.
from .. import service_testing as st


class OsAgent(st.CliAgent):
  """A service_testing.CliAgent that uses the OpenStackClient tool to interact with OpenStack.
  See https://docs.openstack.org/developer/python-openstackclient/man/openstack.html for
  more information on the OpenStackClient.

  Attributes:
    os_cloud: The cloud to use from the clouds.yaml file to use with CLI invocations.
    Clouds are configured in a clouds.yaml file the client looks for in either
    current directory, ~/.config/openstack, or /etc/openstack
  """

  @property
  def os_cloud(self):
    """The os command-line client cloud profile to use."""
    return self.__os_cloud


  def __init__(self, os_cloud, trace=True):
    """Construct instance.

    Args:
      profile: The OpenStackClient command --os-cloud name to use by default.
      trace: Whether to trace all I/O by default.
    """
    super(OsAgent, self).__init__('openstack')
    self.__os_cloud = os_cloud
    self.trace = trace
    self.logger = logging.getLogger(__name__)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    builder.make_control(entity, 'Cloud', self.__os_cloud)
    builder.make_control(entity, 'Trace', self.trace)
    super(OsAgent, self).export_to_json_snapshot(snapshot, entity)

  def build_os_command_args(self, os_command, args,
                            os_cloud=None):
    """Build commandline for a given resource type, independent of the action.

    Args:
      os_cloud: If specified, include an --os_cloud, otherwise do not.
      os_command: The openstack command name we are going to execute.
      args: The arguments following os_command.


    Returns:
      list of complete command line arguments following implied 'openstack'
    """
    if not os_cloud:
      os_cloud = self.__os_cloud

    preamble = []
    if os_cloud:
      preamble += ['--os-cloud', os_cloud]

    return preamble + [os_command] + args

  def run_resource_list_commandline(self, command_args, root_key, trace=True):
    """Runs the given command and returns the json resource list.

    Args:
      command_args: The commandline returned by build_os_command_args
      root_key: The key in the resulting command output containing the list
         to return. If empty, return the whole document.
    Raises:
      ValueError if the command fails

    Returns:
      List of objects from the command.
    """
    os_response = self.run(command_args, trace)
    if not os_response.ok():
      raise ValueError(os_response.error)

    decoder = json.JSONDecoder()
    doc = decoder.decode(os_response.output)
    return doc[root_key] if root_key else doc

  def get_resource_list(self, context, root_key, os_command, args,
                        os_cloud=None, trace=True):
    """Returns a resource list returned when executing the openstack commandline.

    This is a combination of build_os_command_args and
    run_resource_list_commandline.
    """
    args = context.eval(args)
    args = self.build_os_command_args(os_command=os_command, args=args,
                                      os_cloud=os_cloud)
    return self.run_resource_list_commandline(args, root_key, trace=trace)

  def get_resource(self, os_command, resource_name, os_cloud=None):
    """Provides information of the OpenStack resource in a json format

    Args:
      command: The openstack command name to run (e.g. 'security group', 'server').
      resource_name: Name of the OpenStack resource (e.g. Name of a security group or a image).
      os_cloud: OpenStack cloud name.
    """
    args = ['show', resource_name, '--format', 'json']
    args = self.build_os_command_args(os_command=os_command, args=args,
                                      os_cloud=os_cloud)
    return self.run_resource_list_commandline(args, None)
