# Base agent for Azure CITest scenario
# pylint: disable=W0311

"""Adapts citest CliAgent to interact with Microsoft Azure using AZ 2.0 CLI"""

 # Python modules
import logging

# CITest Modules

from ..service_testing import cli_agent

class AzAgent(cli_agent.CliAgent):
  """ The Agent that uses az 2.0 cli to interact with Azure Cloud. """

  def __init__(self, trace=True):
    """ Construct the instance

    Attributes:
      trace: Wether to trace all I/O by default
    """

    # Local path of the AZ CLI
    super(AzAgent, self).__init__('az')
    # Activate the logging and trace
    self.trace = trace
    self.logger = logging.getLogger(__name__)

  def build_az_command_args(self, az_resource, az_command, args):

    """"Build the Azure command line to be used

    Attributes:
      az_resource: The az resource module name (group, vm, etc...)
      az_command: The az action on the resource (list, add, etc..)
      args: All the others args after the command (-g, -n, -l, etc...)
    """

    preamble = []
    globalcmd = [az_resource, az_command] + args
    return preamble + globalcmd
