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
from ..service_testing import cli_agent
from ..service_testing import testable_agent


class PassphraseInjector(object):
  """Monitors a file descriptor and injects passphrases as requested."""

  def __init__(self, fd, ssh_passphrase_file=None, daemon=False):
    """Constructor

    Args:
      fd: The file descriptor to read from (and write to).
      ssh_passphrase_file: Contains passphrase to inject.
          If no passphrases are expected (e.g. ssh-agent is running)
          then this could be nullptr.
      daemon: If true then the injector should never terminate.
          Otherwise, it will terminate once there is no more input.
    """
    self._fd = fd
    self._ssh_passphrase_file = ssh_passphrase_file
    self._daemon = daemon
    self._logger = logging.getLogger(__name__)

  def __call__(self):
    """Reads from the bound fd and injects the passphrase when asked.

    Returns:
        A string of the entire output from fd, minus passphrase prompts.
    """
    passphrase = None
    try:
      if self._ssh_passphrase_file:
        with file(self._ssh_passphrase_file) as f:
          passphrase = f.read()
          if passphrase[-1] != '\n':
            passphrase += '\n'
    except:
      self._logger.error(
          '--ssh_passphrase_file=%s not found', self._ssh_passphrase_file)
      sys.exit(-1)

    return self._read_process_output(passphrase)

  def _read_process_output(self, passphrase):
    lines = []
    trigger_regex = re.compile('Enter passphrase for key ');

    injected = False
    output = ''
    while True:
      try:
        ch = os.read(self._fd, 1)
      except OSError:
        ch = None

      if not ch:
        if self._daemon:
          continue
        break

      if not injected and trigger_regex.search(output):
        self._logger.debug('(Injecting Passphrase into ssh)')
        if not passphrase:
          self._logger.error(
              'SSH wants a passphrase, but --ssh_passphrase_file not provided.')
          sys.exit(-1)
        os.write(self._fd, passphrase)
        injected = True
      if ch == '\r':
        continue
      if ch != '\n':
        output += ch
        continue

      if self._daemon:
        self._logger.debug('(from ssh): %r', output)
      else:
        if injected:
          self._logger.debug('(from ssh): %r', output)
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
  _LIST_NEEDS_ZONE = ['managed-instance-groups']
  _DESCRIBE_NEEDS_ZONE = _LIST_NEEDS_ZONE + ['instances']
  _PREVIEW_GROUPS = ['managed-instance-groups']

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
      return gce_type in GCloudAgent._LIST_NEEDS_ZONE
    if gcloud_command == 'describe':
      return gce_type in GCloudAgent._DESCRIBE_NEEDS_ZONE
    return False

  @property
  def project(self):
    return self._project

  @property
  def zone(self):
    return self._zone

  def __init__(self, project, zone, ssh_passphrase_file='', trace=True):
    """Construct instance.

    Args:
      project: The name of the GCP project this agent will run against.
      zone: The default GCP zone this agent will interact with.
      ssh_passphrase_file: The path to a file that contains the SSH passphrase.
          This is optional, but if provided then it allows the agent to log
          into instances if needed in order to tunnel through firewalls to
          gain access to test internal subsystems or execute remote commands.
          You can run ssh-agent as an alternative.
          The file should be made user read-only (400) for security.
      trace: Whether to trace all the calls by default for debugging.
    """
    super(GCloudAgent, self).__init__('gcloud')
    self._project = project
    self._zone = zone
    self._ssh_passphrase_file = ssh_passphrase_file
    self.trace = trace
    self.logger = logging.getLogger(__name__)

  def _make_scribe_parts(self, scribe):
    parts = [
      scribe.build_part('Project', self._project),
      scribe.build_part('Zone', self._zone),
      scribe.build_part('Passphrase File', self._ssh_passphrase_file),
      scribe.build_part('Trace', self._trace)]
    inherited = super(GCloudAgent, self)._make_scribe_parts(scribe)
    return parts + inherited

  @staticmethod
  def is_preview_type(gce_type):
    """Determine if the gce_type a gcloud preview type or not?

    This is so consuming code doesnt need to worry about it or be maintained
    when gcloud updates.

    Args:
      gce_type: The gcloud type we're inquiring about.
    """
    if not GCloudAgent._PREVIEW_GROUPS:
      GCloudAgent._init_preview_groups()
    return gce_type in GCloudAgent._PREVIEW_GROUPS

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
    preamble += [gce_type]

    if not zone:
      args_with_zone = args
    elif GCloudAgent.zone_comes_first(gcloud_module, gce_type):
      args_with_zone = ['--zone', zone] + args
    else:
      args_with_zone = args + ['--zone', zone]

    return preamble + args_with_zone


  def pty_fork_ssh(self, instance, arg_array, async=False):
    """Fork a pseudo-tty and run gcloud compute ssh in it.

    Args:
      instance: The instance to ssh to, using the agents project and zone.
      arg_array: The list of additional gcloud command line argument strings
          following the ssh command.
      async: If true then this shell is intended to act as a long-lived
          daemon thread (e.g. to provide a tunnel), so start the thread with
          a PassphraseInjector that can inject the passphrase if prompted to
          do so. Otherwise this is intended to act as a short-term shell
          synchronized to the current thread (e.g. to execute a remote command)
          and leaves it to the caller to run a PassphraseInjector..
    """
    cmdline = ['gcloud', 'compute', 'ssh', instance,
               '--project', self._project,
               '--zone', self._zone] + arg_array
    bash_command = ['/bin/bash', '-c', ' '.join(cmdline)]
    if self.trace:
      self.logger.debug(bash_command)
    pid, fd = os.forkpty()
    if not pid:
      os.execv(bash_command[0], bash_command)
    if async:
      pi = PassphraseInjector(
          fd=fd, ssh_passphrase_file=self._ssh_passphrase_file, daemon=async)
      t = threading.Thread(target=pi)
      t.setDaemon(True)
      t.start()

    return (pid, fd)

  def remote_command(self, instance, command, trace=True):
    """Run a command on the instance.

    Args:
      instance: The instance to run on.
      command: The command to run as a string.
      trace: False to suppress tracing, otherwise use default.

    Returns:
      cli.CliResponseType with execution results.
    """
    pid, fd = self.pty_fork_ssh(
        instance, ['--command', '"%s"' % command], async=False)
    output = PassphraseInjector(
        fd=fd, ssh_passphrase_file=self._ssh_passphrase_file)()
    retcode = os.waitpid(pid, os.WNOHANG)[1]
    if not retcode:
      return cli_agent.CliResponseType(0, output, '')
    return cli_agent.CliResponseType(retcode, '', output)

  def list_resources(self, gce_type, format='json', extra_args=None):
    """Obtain a list of references to all the GCE resources of a given type.

    Args:
      gce_type: The type of resource to list.
      format: The gcloud --format type.
      extra_args: Array of extra arguments for the list command
          to tack onto command line, or None.

    Returns:
      cli.CliRunStatus with execution results.
    """
    needs_zone = gce_type in self._LIST_NEEDS_ZONE
    args = ['list'] + (extra_args or [])
    cmdline = self.build_gcloud_command_args(
      gce_type, args, format=format, project=self._project,
      zone=self._zone if needs_zone else None)
    return self.run(cmdline, self.trace)


  def describe_resource(self, gce_type, name, format='json', extra_args=None):
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
    needs_zone = gce_type in self._DESCRIBE_NEEDS_ZONE
    args = ['describe', name] + (extra_args or [])
    cmdline = self.build_gcloud_command_args(
        gce_type, args, format=format, project=self._project,
        zone=self._zone if needs_zone else None)

    return self.run(cmdline, self.trace)

  def run(self, args, trace=True):
    """Run the specified command.

    This implements the CliAgent.run() method.

    Args:
      args: Complete list of command-line arguments to run.
      trace: Whether or not to trace all I/O to the debugging log file.
    """
    # We're only overriding this method to work around a bug in gcloud.
    status = super(GCloudAgent, self).run(args, trace)
    try:
      output = status.output
      if (output
          and 'managed-instance-groups' in args
          and 'describe' in args
          and args[1 + args.index('--format')] == 'json'):
        # There's a bug b/21363050 where gcloud is returning JSON as []{}.
        # Work around that here by stripping off the leading [].
        unexpected_array = output.find('\n]')
        if unexpected_array > 0:
          output = output[unexpected_array + 2:]
          logger = logging.getLogger(__name__)
          logger.debug(
             '*** Working around b/21363050 by transforming JSON to:\n%s',
             output)
          return status.__class__(status.retcode, output, status.error)
    except:
      pass
    return status
