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


# Standard python modules.
import logging

# Our modules.
import citest.service_testing.cli_agent as cli_agent
from citest.base.json_scrubber import JsonScrubber

class KubeCtlAgent(cli_agent.CliAgent):
  """Agent that uses kubectl program to interact with Kubernetes."""

  def __init__(self, logger=None):
    """Construct instance.

    Args:
      logger: The logger to inject if other than the default.
    """
    logger = logger or logging.getLogger(__name__)
    super(KubeCtlAgent, self).__init__(
        'kubectl', output_scrubber=JsonScrubber(), logger=logger)

  @staticmethod
  def build_kubectl_command_args(action, resource=None, args=None):
    """Build commandline for an action.

    Args:
      action: The operation we are going to perform on the resource.
      resource: The kubectl resource we are going to operate on (if applicable).
      args: The arguments following [gcloud_module, gce_type].

    Returns:
      list of complete command line arguments following implied 'kubectl'
    """
    return [action] + ([resource] if resource else []) + (args if args else [])

  def list_resources(self, context, kube_type, format='json', extra_args=None):
    """Obtain a list of references to all Kubernetes resources of a given type.

    Args:
      kube_type: The type of resource to list.
      format: The kubectl --format type.
      extra_args: Array of extra arguments for the list command
          to tack onto command line, or None.

    Returns:
      cli.CliRunStatus with execution results.
    """
    args = ['--output', format] + (extra_args or [])
    args = context.eval(args)
    cmdline = self.build_kubectl_command_args(
        action='get', resource=kube_type, args=args)
    return self.run(cmdline)
