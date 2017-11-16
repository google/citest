# Base agent for Azure CITest scenario
# pylint: disable=W0311

"""Adapts citest CliAgent to interact with Microsoft Azure using AZ 2.0 CLI"""

 # Python modules
import logging

# CITest Modules

import citest.service_testing.cli_agent as cli_agent

class AzAgent(cli_agent.CliAgent):
  """ The Agent that uses az 2.0 cli to interact with Azure Cloud. """

  def __init__(self, logger=None):
    """ Construct the instance

    Attributes:
      logger: Inject this logger into the agent rather than using the default.
    """
    # Local path of the AZ CLI
    logger = logger or logging.getLogger(__name__)
    super(AzAgent, self).__init__('az', logger=logger)

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
