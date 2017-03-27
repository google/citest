# Copyright 2017 Google Inc. All Rights Reserved.
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

"""Helper classes and methods for peeking at journals.

This is particular to the JSON emitted by the Journal.
"""

import argparse
import math
import sys


from citest.reporting.journal_processor import (
    JournalProcessor)


def level_prefix(level, nub='+ '):
  """Determine line prefix for the given level.

  Args:
    level: [int]  Depth to indent.
    nub: [string] trailing text at the end of the indent.
  """
  if not level:
    return ''
  return '{preamble}  {nub}'.format(preamble='  |' * (level - 1), nub=nub)


class DumpRenderer(JournalProcessor):
  """Class that renders a journal to text dump.

  This is a text renderer, but focuses on the structure of the journal entries
  rather than trying to communicate their context.
  """

  @property
  def first_line_prefix(self, num='+ '):
    """Determine output prefix, such as indentation, for an entry."""
    return level_prefix(len(self.__context_stack), nub=num)

  @property
  def continuation_prefix(self, nub='  ... '):
    """Determine output prefix, such as indentation, for lines within an entry.
    """
    prototype = level_prefix(len(self.__context_stack), nub='')
    return ' ' * len(prototype) + nub

  def __init__(self, options, registry=None):
    """Constructor.

    Args:
      options: [dict] Configuration options
      registry: See JournalProcessor
    """
    if registry is None:
      registry = {
          'JsonSnapshot': self.render_snapshot,
          'JournalContextControl': self.render_context_control,
          'JournalMessage': self.render_message
      }
    super(DumpRenderer, self).__init__(registry)
    self.__context_stack = []
    self.__outline = options.get('outline', False)
    self.__details = options.get('details', False)
    self.__start_time = None


  def emit(self, entry, literal=False, **kwargs):
    """Prints a block of output."""
    time = kwargs.get('time')
    if time:
      if not self.__start_time:
        self.__start_time = time
      time_text = 't={0}: '.format(str(round(time - self.__start_time, 3)))
    else:
      time_text = ''

    text = entry.format(**kwargs)
    if not literal:
      text = text.replace('\n', '\n%s' % self.continuation_prefix)
    print '{prefix}{time}{text}'.format(
        prefix=self.first_line_prefix, time=time_text, text=text)

  def terminate(self):
    """Implements JournalProcessor interface."""
    if self.__context_stack:
      raise ValueError(
          'Still have {0} open contexts'.format(len(self.__context_stack)))

  def render_snapshot(self, snapshot):
    """Render a snapshot entry."""
    subject_id = snapshot.get('_subject_id')
    entities = snapshot.get('_entities', {})
    if self.__outline:
      self.emit('SNAPSHOT of {subject} has {count} entities.',
                subject=subject_id, count=len(entities))
    else:
      subject_id = snapshot.get('_subject_id')
      entities = snapshot.get('_entities', {})
      relation = entities.get(subject_id, {}).get('_default_relation')
      padding = ' ' * int(math.ceil(math.log(len(entities) + 1, 10)))
      level = len(self.__context_stack) + 1
      lines = []
      for entity_id, entity in sorted(entities.items(),
                                      lambda a, b: int(a[0]) - int(b[0])):
        nub = '{padding}{id}: '.format(padding=padding[:-len(entity_id)],
                                       id=entity_id)
        prefix = level_prefix(level, nub=nub)
        lines.append('{prefix}{text}'.format(
            prefix=prefix, text=self.snapshot_entity_to_string(entity)))
      self.emit('SNAPSHOT of #{subject} relation={relation}:\n{text}',
                literal=True,
                subject=subject_id, relation=relation,
                text='\n'.join(lines))

  def __edge_details_to_string(self, indent, edges):
    if not self.__details:
      return ''
    lines = []
    for edge in edges:
      label = edge.get('label')
      if '_value' in edge.keys():
        kind = '_value'
        value = edge['_value']
      elif '_to' in edge.keys():
        kind = '_to'
        value = edge['_to']
      else:
        kind = 'n/a'
        value = ''
      lines.append('\n{indent}{relation} {kind} {label}={value}'.format(
          indent=indent,
          label=label,
          kind=kind,
          value=value,
          relation=edge.get('relation', '<default>')))
    return ''.join(lines)

  def snapshot_entity_to_string(self, entity):
    """Render entity as a string."""
    title = entity.get('_title')
    entity_edges = entity.get('_edges', [])
    edge_names = [edge.get('label') for edge in entity_edges]
    summary = []
    if title:
      summary.append('title={title!r}'.format(title=title))
    if edge_names:
      indent = ' ' * (len(entity.get('class', 'UNDEFINED'))
                      + len(self.continuation_prefix) - 3)
      edge_detail = self.__edge_details_to_string(indent, entity_edges)
      summary.append('edges={edge_names}{edge_detail}'.format(
          edge_names=edge_names, edge_detail=edge_detail))

    return '{type} {summary}'.format(
        type=entity.get('class', 'UNDEFINED').replace('type ', ''),
        summary=' '.join(summary))

  def render_context_control(self, control):
    """Render a context control entry."""
    direction = control['control']
    if direction == 'BEGIN':
      title = control.get('_title')
    else:
      original = self.__context_stack[-1]
      title = original.get('_title')
      self.__context_stack.pop()

    self.emit('CONTEXT {direction} {title}',
              direction=direction, title=title)

    if direction == 'BEGIN':
      self.__context_stack.append(control)

  def render_message(self, message):
    """Render a message entry."""
    text = message.get('_value').strip()
    format_spec = message.get('format', None)
    time = message.get('_timestamp', None)
    optional_format = ('{{format={0}}}'.format(format_spec)
                       if format_spec
                       else '')

    if self.__outline:
      self.emit('MESSAGE{format} len={len}',
                format=optional_format, len=len(text))
    else:
      self.emit('{format} {text!r}',
                time=time, format=optional_format, text=text)


def main(argv):
  """Main program for dumping as text."""
  parser = argparse.ArgumentParser()
  parser.add_argument('--details', default=False, action='store_true',
                      help='Show all the details.')
  parser.add_argument('--outline', default=False, action='store_true',
                      help='Show an outline only.')
  parser.add_argument('journals', metavar='PATH', type=str, nargs='+',
                      help='list of journals to process')
  options = parser.parse_args(argv[1:])
  for path in options.journals:
    processor = DumpRenderer(vars(options))
    processor.process(path)
    processor.terminate()


if __name__ == '__main__':
  main(sys.argv)
