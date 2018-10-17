# Copyright 2018 Google Inc. All Rights Reserved.
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

"""Manipulates journal files.

Provides commands for manipulating journal files. The primary purposes are

   1) To dump file content for inspection or debugging
   2) To create journal files to indicate that tests could not be run.
      Normally journal files are created while running tests. However if
      the tests cannot be run at all (e.g. precondition failed in a launcher)
      then there is no way to indicate that through citest output since citest
      wont even be called.
"""

import argparse
import json
import sys
import yaml

try:
  from StringIO import StringIO
except ImportError:
  from io import StringIO


from citest.base import Journal, StreamJournalNavigator
from citest.reporting import DumpRenderer


def load_metadata(path):
  """Return the contents of a YAML or JSON path."""
  metadata = {}
  if path:
    with open(path, 'r') as stream:
      content = stream.read()
    try:
      doc = yaml.safe_load(StringIO(content))
    except (TypeError, ValueError, UnicodeEncodeError):
      doc = json.load(StringIO(content))
    metadata.update(doc)
        
  return metadata


class JournalCommand(object):
  """Base class for commands that operate on journals."""

  @property
  def name(self):
    """Returns the command name."""
    return self.__name

  def __init__(self, name, help=None):
    self.__name = name
    self.__help = help


  def init_argument_parser(self, argparser):
    """Initialize command-line arguments."""
    parser = argparser.add_parser(self.__name, help=self.__help)
    parser.add_argument(
        '--path', required=True,
        help='The path to the journal to operate on.')
    return parser


class WriteCommand(JournalCommand):
  """Base class for commands that write to journals."""

  def __init__(self, *pos_args, **kwargs):
    self.__creates_file = kwargs.pop('creates_file', False)
    self.__writes_records = kwargs.pop('writes_record', True)
    super(WriteCommand, self).__init__(*pos_args, **kwargs)

  def open_journal(self, options):
    """Opens an existing journal for appending."""
    journal = Journal()
    journal.open_with_path(options.path, _append=True, _message=None)
    return journal

  def get_record_metadata(self, options):
    """Extract metadata from options."""
    doc = {}
    if options.metadata_path:
      doc.update(load_metadata(options.metadata_path))
    if options.metadata:
      doc.update(json.JSONDecoder(encoding='utf-8').decode(options.metadata))
    return doc

  def get_journal_metadata(self, options):
    """Extract metadata from options."""
    doc = {}
    if options.journal_metadata_path:
      doc.update(load_metadata(options.journal_metadata_path))
    if options.journal_metadata:
      doc.update(
          json.JSONDecoder(encoding='utf-8').decode(options.journal_metadata))
    return doc

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(WriteCommand, self).init_argument_parser(argparser)
    parser.add_argument('--metadata_path',
                        help='Path to yaml (or json) file containing metadata.')
    parser.add_argument('--metadata',
                        help='JSON encoded record metadata.')
    if self.__creates_file:
      parser.add_argument(
          '--journal_metadata_path',
          help='Path to yaml (or json) file containing metadata for journal.')
      parser.add_argument(
          '--journal_metadata',
          help='JSON encoded journal metadata.')
    return parser


class BeginContextCommand(WriteCommand):
  """Start a new context in the journal."""

  def __init__(self):
    super(BeginContextCommand, self).__init__(
        'begin_context', 'Start a new context.')

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(BeginContextCommand, self).init_argument_parser(argparser)
    parser.add_argument('title', help='The context title.')

  def __call__(self, options):
    """Process command."""
    journal = self.open_journal(options)
    journal.begin_context(options.title, **self.get_record_metadata(options))
    journal.terminate(_message=None)


class EndContextCommand(WriteCommand):
  """End the current context in the journal."""

  def __init__(self):
    super(EndContextCommand, self).__init__(
        'end_context', help='End the current context.')

  def __call__(self, options):
    """Process command."""
    journal = self.open_journal(options)
    journal.end_context(**self.get_record_metadata(options))
    journal.terminate(_message=None)


class MessageCommand(WriteCommand):
  """Append a message into the journal."""

  def __init__(self):
    super(MessageCommand, self).__init__(
        'append',
        help='Append a message into a journal.')

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(MessageCommand, self).init_argument_parser(argparser)
    parser.add_argument(
        'message',
        help='The message to write into the journal.')
    parser.add_argument(
        '--context',
        help='Context title for message, if any.')
    parser.add_argument(
        '--seal',
        help='Seal the journal with a final termination message.')

  def __call__(self, options):
    """Process command."""
    journal = self.open_journal(options)
    terminate_metadata = {}
    if not options.seal:
      terminate_metadata = {'_message': None}
    try:
      if options.context:
        journal.begin_context(options.context)
      journal.write_message(options.message, **self.get_record_metadata(options))
    finally:
      if options.context:
        journal.end_context()
      journal.terminate(**terminate_metadata)


class NewCommand(WriteCommand):
  """Create a new journal file."""

  def __init__(self):
    super(NewCommand, self).__init__(
        'new',
        help='Start a new journal file.',
        creates_file=True, writes_record=False)

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(NewCommand, self).init_argument_parser(argparser)
    parser.add_argument(
        '--message', default=None, help='Initial message if customized.')

  def __call__(self, options):
    """Process command."""
    args = dict(self.get_journal_metadata(options))
    if options.message:
      args['_message'] = options.message

    journal = Journal()
    journal.open_with_path(options.path, **args)
    journal.terminate(_message=None)


class SealCommand(WriteCommand):
  """Terminate a journal with a final message."""

  def __init__(self):
    super(SealCommand, self).__init__(
        'seal',
        help='Write termination message into the journal.')

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(SealCommand, self).init_argument_parser(argparser)
    parser.add_argument(
        '--message', default=None, help='Final message if customized.')

  def __call__(self, options):
    """Process command."""
    journal = self.open_journal(options)
    message = options.message
    if message:
      journal.terminate(_message=message, **self.get_record_metadata(options))
    else:
      journal.terminate()


class MakeErrorCommand(WriteCommand):
  """Create a journal designating an error."""
  def __init__(self):
    super(MakeErrorCommand, self).__init__(
        'make_error',
        help='Create a journal designating an error'
        ', such as unable to execute the command that would have'
        ' written the expected journal.',
        creates_file=True)

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(MakeErrorCommand, self).init_argument_parser(argparser)
    parser.add_argument(
        '--title', default=None, help='The context title, if any.')
    parser.add_argument(
        '--message', required=True, help='The message.')

  def __call__(self, options):
    journal = Journal()
    journal.open_with_path(
        options.path, **self.get_journal_metadata(options))
    journal.begin_context(options.title or 'Error')
    try:
      journal.write_message(
          options.message, **self.get_record_metadata(options))
    finally:
      journal.end_context(relation='ERROR')
      journal.terminate()


class DumpCommand(JournalCommand):
  """Dump an existing journal."""

  def __init__(self):
    super(DumpCommand, self).__init__(
        'dump',
        help='Dump the contents of a journal.')

  def init_argument_parser(self, argparser):
    """Adds arguments."""
    parser = super(DumpCommand, self).init_argument_parser(argparser)
    parser.add_argument('--details', default=False, action='store_true',
                        help='Show all the details.')
    parser.add_argument('--outline', default=False, action='store_true',
                        help='Show an outline only.')


  def __call__(self, options):
    """Process command."""
    navigator = StreamJournalNavigator.new_from_path(options.path)
    processor = DumpRenderer(vars(options))
    processor.process(navigator)
    processor.terminate()


def not_found(options):
  """Handles unknown commands."""
  sys.stderr.write('"%s" is not a vaild command.\n' % options['command'])


def main(argv):
  """Program controller."""
  commands = {
      command.name: command
      for command in [
          BeginContextCommand(),
          EndContextCommand(),
          MessageCommand(),
          NewCommand(),
          SealCommand(),
          MakeErrorCommand(),
          DumpCommand()
      ]
  }

  parser = argparse.ArgumentParser(
      description='Helper tool to interact with citest journals.')
  subparsers = parser.add_subparsers(title='commands', dest='command')
  for cmd in set(commands.values()):
    cmd.init_argument_parser(subparsers)

  options = parser.parse_args(argv)
  command = commands.get(options.command, not_found)
  command(options)
  sys.exit(-1 if command == not_found else 0)


if __name__ == '__main__':
  main(sys.argv[1:])
