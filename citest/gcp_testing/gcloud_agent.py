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
import citest.service_testing.cli_agent as cli_agent
from citest.base.json_scrubber import JsonScrubber

class PassphraseInjector(object):
  """Monitors a file descriptor and injects passphrases as requested."""
  # pylint: disable=too-few-public-methods

  def __init__(self, fd, ssh_passphrase_file=None, daemon=False, logger=None):
    """Constructor

    Args:
      fd: The file descriptor to read from (and write to).
      ssh_passphrase_file: Contains passphrase to inject.
          If no passphrases are expected (e.g. ssh-agent is running)
          then this could be nullptr.
      daemon: If true then the injector should never terminate.
          Otherwise, it will terminate once there is no more input.
      logger: The logger to use if other than the default.
    """
    self.__fd = fd
    self.__ssh_passphrase_file = ssh_passphrase_file
    self.__daemon = daemon
    self.__logger = logger or logging.getLogger(__name__)

  def __call__(self):
    """Reads from the bound fd and injects the passphrase when asked.

    Returns:
        A string of the entire output from fd, minus passphrase prompts.
    """
    passphrase = None
    try:
      if self.__ssh_passphrase_file:
        with open(self.__ssh_passphrase_file) as stream:
          passphrase = stream.read()
          if passphrase[-1] != '\n':
            passphrase += '\n'
    except IOError as ioex:
      self.__logger.error(
          'ERROR with --ssh_passphrase_file=%s: %s',
          self.__ssh_passphrase_file, ioex)
      sys.exit(-1)

    return self.__read_process_output(passphrase)

  def __read_process_output(self, passphrase):
    """Collect output from subprocess, injecting passphrase when prompted."""
    lines = []
    trigger_regex = re.compile('Enter passphrase for key ')

    injected = False
    output = ''
    while True:
      try:
        value = os.read(self.__fd, 1)
      except OSError:
        value = None

      if not value:
        if self.__daemon:
          continue
        break

      if not injected and trigger_regex.search(output):
        self.__logger.debug('(Injecting Passphrase into ssh)')
        if not passphrase:
          self.__logger.error(
              'SSH wants a passphrase, but --ssh_passphrase_file not provided.')
          sys.exit(-1)
        os.write(self.__fd, passphrase)
        injected = True
      if value == '\r':
        continue
      if value != '\n':
        output += value
        continue

      if self.__daemon:
        self.__logger.debug('(from ssh): %r', output)
      else:
        if injected:
          self.__logger.debug('(from ssh): %r', output)
        else:
          lines.append(output)
      injected = False
      output = ''

    lines.append(output)
    return '\n'.join(lines)


class GCloudAgent(cli_agent.CliAgent):
  """Agent that uses gcloud program to interact with Google Cloud Platform.

  Attributes:
    project: The default GCP project to use.
    zone: The default GCP zone to use (for commands requiring one).
  """
  __LIST_NEEDS_ZONE = ['managed-instance-groups', 'unmanaged-instance-groups']
  __DESCRIBE_NEEDS_ZONE = __LIST_NEEDS_ZONE + ['instances']
  __PREVIEW_COMMANDS = []

  @staticmethod
  def command_needs_zone(gce_type, gcloud_command, gcloud_type='compute'):
    """Determine if gcloud command needs a --zone parameter.

    Args:
      gce_type: The gce resource type we're operating on (e.g. 'instances')
      gcloud_command: The gcloud command name (e.g. 'list')
      gcloud_type: The gcloud command namespace name (e.g. 'compute')

    Returns:
      True if we need a --zone, False otherwise.
    """
    if gcloud_command == 'list':
      return gce_type in GCloudAgent.__LIST_NEEDS_ZONE
    if gcloud_command == 'describe':
      return gce_type in GCloudAgent.__DESCRIBE_NEEDS_ZONE
    return False

  @property
  def project(self):
    """The default GCP project that this agent will interact with."""
    return self.__project

  @property
  def zone(self):
    """The default GCP zone that this agent will interact with."""
    return self.__zone

  def __init__(self, project, zone, service_account=None,
               ssh_passphrase_file='', logger=None):
    """Construct instance.

    Args:
      project: The name of the GCP project this agent will run against.
      zone: The default GCP zone this agent will interact with.
      service_account: If provided, the GCP service account that the agent
          should authenticate with. This must have already been activated
          with the local gcloud using gcloud auth activate-service-account.
          If no account is provided, the configured default account will be
          used. To change the default account, use gcloud config set account.
      ssh_passphrase_file: The path to a file that contains the SSH passphrase.
          This is optional, but if provided then it allows the agent to log
          into instances if needed in order to tunnel through firewalls to
          gain access to test internal subsystems or execute remote commands.
          You can run ssh-agent as an alternative.
          The file should be made user read-only (400) for security.
      logger: The logger to inject if other than the default.
    """
    logger = logger or logging.getLogger(__name__)
    super(GCloudAgent, self).__init__(
        'gcloud', output_scrubber=JsonScrubber(), logger=logger)
    self.__project = project
    self.__zone = zone
    self.__ssh_passphrase_file = ssh_passphrase_file
    self.__service_account = service_account

  def _args_to_full_commandline(self, args):
    if self.__service_account:
      args = ['--account', self.__service_account] + args

    return super(GCloudAgent, self)._args_to_full_commandline(args)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    builder.make_control(entity, 'Project', self.__project)
    builder.make_control(entity, 'Zone', self.__zone)
    builder.make_control(entity, 'Passphrase File', self.__ssh_passphrase_file)
    super(GCloudAgent, self).export_to_json_snapshot(snapshot, entity)

  @staticmethod
  def is_preview_type(gce_type):
    """Determine if the gce_type a gcloud preview type or not?

    This is so consuming code doesnt need to worry about it or be maintained
    when gcloud updates.

    Args:
      gce_type: The gcloud type we're inquiring about.
    """
    return gce_type in GCloudAgent.__PREVIEW_COMMANDS

  @staticmethod
  def zone_comes_first(gce_module, gce_type):
    """Does --zone come before the |gce_type| on the commandline, or after?

    Args:
      gce_module: The name of the |gce_module| in the gcloud command
         (e.g. 'compute').
      gce_type: The type of GCE resource (as used by gcloud).
    """
    return gce_module == 'preview'

  @staticmethod
  def build_gcloud_command_args(gce_type, args, gcloud_module=None,
                                format='json', project=None, zone=None):
    """Build commandline for a given resource type, independent of the action.

    Args:
      gce_type: The gcloud type name we are going to operate on.
      args: The arguments following [gcloud_module, gce_type].
      gcloud_module: which gcloud <module> to run. If empty, we'll infer it.
      format: The gcloud --format we want.
      project: If specified, include an --project, otherwise dont.
      zone: If defined, then add this as the --zone.
          We're calling 'zone' out as a special argument because its placement
          is inconsistent depending on the gce_type.

    Returns:
      list of complete command line arguments following implied 'gcloud'
    """
    if not gcloud_module:
      if GCloudAgent.is_preview_type(gce_type):
        gcloud_module = 'preview'
      else:
        gcloud_module = 'compute'
    preamble = ['-q', gcloud_module, '--format', format]
    if project:
      preamble += ['--project', project]
    if gce_type == 'managed-instance-groups':
      preamble += ['instance-groups', 'managed']
    elif gce_type == 'unmanaged-instance-groups':
      preamble += ['instance-groups', 'unmanaged']
    else:
      preamble += [gce_type]

    if not zone:
      args_with_zone = args
    elif GCloudAgent.zone_comes_first(gcloud_module, gce_type):
      args_with_zone = ['--zone', zone] + args
    else:
      args_with_zone = args + ['--zone', zone]

    return preamble + args_with_zone


  def pty_fork_ssh(self, instance, arg_array, asynchronous=False):
    """Fork a pseudo-tty and run gcloud compute ssh in it.

    Args:
      instance: The instance to ssh to, using the agents project and zone.
      arg_array: The list of additional gcloud command line argument strings
          following the ssh command.
      asynchronous: If true then this shell is intended to act as a long-lived
          daemon thread (e.g. to provide a tunnel), so start the thread with
          a PassphraseInjector that can inject the passphrase if prompted to
          do so. Otherwise this is intended to act as a short-term shell
          synchronized to the current thread (e.g. to execute a remote command)
          and leaves it to the caller to run a PassphraseInjector..
    """
    cmdline = ['gcloud']
    if self.__service_account:
      cmdline.extend(['--account', self.__service_account])
    cmdline.extend(['compute', 'ssh', instance,
                    '--project', self.__project,
                    '--zone', self.__zone])
    cmdline.extend(arg_array)

    bash_command = ['/bin/bash', '-c', ' '.join(cmdline)]
    self.logger.debug(bash_command)
    pid, fd = os.forkpty()
    if not pid:
      os.execv(bash_command[0], bash_command)
    if asynchronous:
      pi = PassphraseInjector(
          fd=fd, ssh_passphrase_file=self.__ssh_passphrase_file, daemon=asynchronous,
          logger=self.logger)
      t = threading.Thread(target=pi)
      t.setDaemon(True)
      t.start()

    return (pid, fd)

  def remote_command(self, instance, command):
    """Run a command on the instance.

    Args:
      instance: The instance to run on.
      command: The command to run as a string.

    Returns:
      cli.CliResponseType with execution results.
    """
    escaped_command = command.replace('"', '\\"').replace('$', '\\$')
    pid, fd = self.pty_fork_ssh(
        instance, ['--command', '"%s"' % escaped_command], asynchronous=False)
    output = PassphraseInjector(
        fd=fd, ssh_passphrase_file=self.__ssh_passphrase_file)()
    exit_code = os.waitpid(pid, os.WNOHANG)[1]
    if not exit_code:
      return cli_agent.CliResponseType(0, output, '')
    return cli_agent.CliResponseType(exit_code, '', output)

  def list_resources(self, context, gce_type, format='json', extra_args=None):
    """Obtain a list of references to all the GCE resources of a given type.

    Args:
      gce_type: The type of resource to list.
      format: The gcloud --format type.
      extra_args: Array of extra arguments for the list command
          to tack onto command line, or None.

    Returns:
      cli.CliRunStatus with execution results.
    """
    needs_zone = gce_type in self.__LIST_NEEDS_ZONE
    args = ['list'] + (context.eval(extra_args) or [])
    cmdline = self.build_gcloud_command_args(
        gce_type, args, format=format, project=self.__project,
        zone=self.__zone if needs_zone else None)
    return self.run(cmdline)

  def describe_resource(self, context, gce_type, name,
                        format='json', extra_args=None):
    """Obtain a description of a GCE resource instance.
    Args:
      gce_type: The type of resource to describe.
      name: The name of the specific resource instance to describe.
      format: The gcloud --format type.
      extra_args: array of extra arguments for the describe command
         to tack onto command line or None.

    Returns:
      cli.CliRunStatus with execution results.
    """
    needs_zone = gce_type in self.__DESCRIBE_NEEDS_ZONE
    args = ['describe', name] + (extra_args or [])
    args = context.eval(args)
    cmdline = self.build_gcloud_command_args(
        gce_type, args, format=format, project=self.__project,
        zone=self.__zone if needs_zone else None)

    return self.run(cmdline)
