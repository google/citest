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


# Standard python modules.
import logging
import os
import re
import sys
import threading

# Our modules.
from .. import service_testing as st


class AwsAgent(st.CliAgent):
  """A service_testing.CliAgent that uses the aws tool to interact with AWS.

  Attributes:
    profile: The --profile name to use with aws tool invocations.
    region: The default AWS region name to use for commands requiring one.
  """

  @property
  def profile(self):
    return self._profile

  @property
  def region(self):
    return self._region

  def __init__(self, profile, region, trace=True):
    """Construct instance.

    Args:
      profile: The aws command --profile name to use by default.
      region: The AWS region to use by default.
      trace: Whether to trace all I/O by default.
    """
    super(AwsAgent, self).__init__('aws')
    self._profile = profile
    self._region = region
    self.trace = trace
    self.logger = logging.getLogger(__name__)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    builder = snapshot.edge_builder
    builder.make_control(entity, 'Profile', self._profile)
    builder.make_control(entity, 'Region', self._region)
    builder.make_control(entity, 'Trace', self._trace)
    super(AwsAgent, self).export_to_json_snapshot(snapshot, entity)

  def build_aws_command_args(self, aws_command, args, aws_module=None,
                             profile=None, region=None):
    """Build commandline for a given resource type, independent of the action.

    Args:
      profile: If specified, include an --profile, otherwise do not.
      aws_command: The aws command name we are going to execute.
      args: The arguments following [aws_module, aws_command].
      aws_module: which aws <module> to run. If empty, we'll infer it.
      region: If defined, then add this as the --region.

    Returns:
      list of complete command line arguments following implied 'aws'
    """
    if not aws_module:
      aws_module = 'ec2'
    if not profile:
      profile = self._profile
    if not region:
      region = self._region

    preamble = []
    if profile:
      preamble += ['--profile', profile]
    if region:
      preamble += ['--region', region]

    return preamble + [aws_module, aws_command] + args
