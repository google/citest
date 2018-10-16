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

"""Extract timing information from journals.

Given one or more journals, extract out the timing information from major
activities such as running a test, completing an operation, and verifying
a contract.

Sample execution:
  Given a file system of <job>/<platform>/*.journal to import
  cd to the root and run:
      for execution_id in *; do
          for platform in $(cd $execution_id; ls); do
              python ../citest/citest/reporting/extract_test_stats.py \
                     --execution_id=$execution_id \
                     --platform=$platform \
                     --output ${execution_id}_${platform}.json \
                     --influx_url='http://localhost:8086' \
                     $execution_id/$platform/*.journal
          done
      done
"""

import argparse
import collections
import json
import os
import re
import sys

try:
  from urllib2 import urlopen
  from urllib2 import Request
except ImportError:
  from urllib.request import urlopen
  from urllib.request import Request

from citest.base import (
    JournalProcessor,
    StreamJournalNavigator
)


# Stats for an individual wait() call within a test.
WaitStats = collections.namedtuple(
    'WaitStats',
    ['test_case', 'outcome', 'id',
     'duration', 'time_offset', 'timestamp'])

# Stats for an individual verify() call within a test.
# This is usually an individual contract clause.
VerifyStats = collections.namedtuple(
    'VerifyStats',
    ['test_case', 'outcome', 'id', 'condition',
     'duration', 'time_offset', 'timestamp'])


class AttemptRecord(object):
  """Stats for an individual test attempt."""

  # Extract the descriptor of what is being verified.
  # This will be from the title metadata in the journal context.
  EXTRACT_TITLE_REGEX = re.compile('Verifying (?:ContractClause: )?(.+)')

  @property
  def test_case(self):
    """The test case being attempted if known."""
    return self.__test_case or self.__default_test_case

  @test_case.setter
  def test_case(self, test_case):
    """Set (or clear) the test case being attempted."""
    self.__test_case = test_case

  @property
  def start_timestamp(self):
    """The timestamp at which the attempt started."""
    return self.__start_timestamp

  def __init__(self, default_test_case, start_control):
    self.__start_timestamp = start_control['_timestamp']
    self.__waits = []
    self.__verifies = []
    self.__default_test_case = default_test_case
    self.__test_case = None
    self.__duration = None
    self.__timestamp = None

  def add_wait(self, begin_control, end_control):
    """Adds a wait event into the test case.

    Args:
      begin_control: The entry from the journal for the begin context.
      end_control: The entry from the journal for the end context.
    """
    timestamp = end_control['_timestamp']
    duration = timestamp - begin_control['_timestamp']
    offset = timestamp - self.__start_timestamp
    stats = WaitStats(self.test_case,
                      end_control.get('relation') or 'UNKNOWN',
                      len(self.__waits), duration, offset,
                      timestamp)
    self.__waits.append(stats)

  def add_verify(self, begin_control, end_control):
    """Adds a verify event into the test case.

    Args:
      begin_control: The entry from the journal for the begin context.
      end_control: The entry from the journal for the end context.
    """
    timestamp = end_control['_timestamp']
    duration = timestamp - begin_control['_timestamp']
    offset = timestamp - self.__start_timestamp
    title = begin_control['_title']
    match = self.EXTRACT_TITLE_REGEX.match(title)
    condition = match.group(1) if match else title
    stats = VerifyStats(self.test_case,
                        end_control.get('relation') or 'UNKNOWN',
                        len(self.__verifies), condition, duration, offset,
                        timestamp)
    self.__verifies.append(stats)

  def finish(self, end_control):
    """Mark this attempt as finished.

    Args:
      end_control: The entry from the journal for the end context.
    """
    self.__timestamp = end_control['_timestamp']
    self.__duration = end_control['_timestamp'] - self.__start_timestamp

  def to_dict(self):
    """Encode this attempt into a json-encodable dictionary."""
    items = {'timestamp': self.__timestamp}
    if self.__waits:
      items['waits'] = [vars(w) for w in self.__waits]
    if self.__verifies:
      items['verifies'] = [vars(v) for v in self.__verifies]
    return items

  def __str__(self):
    output = []
    if self.__waits:
      output.append('WAITS:')
      for elem in self.__waits:
        output.append(str(elem))
    if self.__verifies:
      output.append('VERIFIES:')
      for elem in self.__verifies:
        output.append(str(elem))
    return ' '.join(output)


class TestRecord(object):
  """Stats for an individual test."""

  # Extract the descriptor of what is being tested.
  # This will be from the title metadata in the journal context.
  EXTRACT_TITLE_REGEX = re.compile('Test "?([^\"]+)"?')

  @property
  def name(self):
    """The name of the test."""
    return self.__name

  @property
  def attempts(self):
    """A list of AttemptRecord."""
    return self.__attempts

  @property
  def duration(self):
    """How long the test took to run."""
    return self.__duration

  @property
  def current_attempt(self):
    """The current AttemptRecord, if any."""
    return self.__current_attempt

  def to_dict(self):
    """Encode this record into a json-encodable dictionary."""
    return {
        'name': self.name,
        'attempts': [attempt.to_dict() for attempt in self.attempts],
        'call_duration': self.duration,
        'timestamp': self.__timestamp,
    }

  def __init__(self, start_control):
    title = start_control['_title']
    match = self.EXTRACT_TITLE_REGEX.match(title)
    self.__name = match.group(1) if match else title
    self.__start_timestamp = start_control['_timestamp']
    self.__timestamp = None
    self.__duration = None
    self.__attempts = []
    self.__current_attempt = None

  def __str__(self):
    output = ['TEST "%s" %d @ %d' % (
        self.__name, len(self.__attempts), self.__duration)]
    for attempt in self.__attempts:
      output.append('ATTEMPT {%s}' % attempt)
    return ' '.join(output)

  def begin_attempt(self, control):
    """Start a new AttemptRecord.

    Args:
      control: The entry from the journal for the begin context.
    """
    self.__current_attempt = AttemptRecord(self.name, control)
    self.__attempts.append(self.__current_attempt)

  def mark_done(self, end_control):
    """Finish this test record.

    Args:
      end_control: The entry from the journal for the end context.
    """
    self.__timestamp = end_control['_timestamp']
    self.__duration = end_control['_timestamp'] - self.__start_timestamp

  def process_activity_control(self, begin_control, end_control):
    """Process an interesting activity context."""
    what = (begin_control.get('_title')
            or begin_control.get('_summary')
            or 'UNDEF')
    if what.startswith('Wait'):
      self.__current_attempt.add_wait(begin_control, end_control)
    elif what.startswith('Verifying '):
      self.__current_attempt.add_verify(begin_control, end_control)
    elif what == 'Execute':
      self.__current_attempt.finish(end_control)
      self.__current_attempt = None


class JournalTimeExtractor(JournalProcessor):
  """Process journals to extract timing of interesting activities."""

  EXTRACT_TITLE_REGEX = re.compile('Test "?([^\"]+)"?')

  @property
  def tests(self):
    """Returns list of TestRecord for all the extracted tests."""
    return self.__tests

  def __ignore(self, _):
    """Ignores entry in journal."""
    pass

  def __init__(self):
    registry = {
        'JsonSnapshot': self.__ignore,
        'JournalContextControl': self.handle_context_control,
        'JournalMessage': self.__ignore
    }
    self.__in_test = None
    self.__tests = []
    self.__context_stack = []
    self.__timestamp = 0
    super(JournalTimeExtractor, self).__init__(registry=registry)

  def __handle_begin_context(self, control):
    self.__context_stack.append(control)
    if len(self.__context_stack) == 1:
      if control.get('_title', '').startswith('Test '):
        self.__in_test = TestRecord(control)
        self.__tests.append(self.__in_test)
    elif control.get('_title', '') == 'Execute':
      self.__in_test.begin_attempt(control)
    elif control.get('_title', '').startswith('Test '):
      title = control['_title']
      match = self.EXTRACT_TITLE_REGEX.match(title)
      self.__in_test.current_attempt.test_case = (
          match.group(1) if match
          else title)

  def __handle_end_context(self, control):
    top = self.__context_stack.pop()
    if not self.__context_stack:
      if self.__in_test:
        self.__in_test.mark_done(control)
        self.__in_test = None
    elif self.__in_test:
      self.__in_test.process_activity_control(top, control)
    elif control.get('_title', '').startswith('Test '):
      self.__in_test.current_attempt.test_case = None

  def handle_context_control(self, control):
    """Process the context control."""
    if control.get('control') == 'BEGIN':
      self.__handle_begin_context(control)
    elif control.get('control') == 'END':
      self.__handle_end_context(control)
    else:
      raise ValueError('Unknown direction "{direction}" in {control!r}'
                       .format(direction=control.get('control'),
                               control=control))


def extract_times(input_path, config_tags):
  """Extract time from path."""
  print('Processing %s' % input_path)
  journal_name = os.path.splitext(os.path.basename(input_path))[0]
  navigator = StreamJournalNavigator.new_from_path(input_path)
  processor = JournalTimeExtractor()
  processor.process(navigator)

  return {
      'config': config_tags,
      'suite': journal_name,
      'tests': [test.to_dict() for test in processor.tests]
  }


def write_to_console(summaries):
  """Write the summaries to stdout."""
  encoder = json.JSONEncoder(indent=2, separators=(',', ': '))
  json_encoding = encoder.encode(summaries)
  print(json_encoding)


def write_to_path(path, summaries):
  """Write the summaries to the given path as JSON."""
  encoder = json.JSONEncoder(indent=2, separators=(',', ': '))
  json_encoding = encoder.encode(summaries)
  with open(path, 'w') as stream:
    stream.write(json_encoding)
  print('WROTE %d summaries to %s' % (len(summaries), path))


def encode_attempt_metrics(attempt, common_tags):
  """Encode the attempt metrics using InfluxDB Line Encoding."""
  metrics = []
  def escape(value):
    """Escape the value for influxdb."""
    return (str(value)
            .replace('"', r'\"')
            .replace(',', r'\,')
            .replace('=', r'\=')
            .replace(' ', r'\ '))

  to_nanos = lambda secs: int(secs * 10**9)

  for wait in attempt.get('waits', []):
    tags = dict(common_tags)
    tags['test_case'] = wait['test_case']
    tags['outcome'] = wait['outcome']
    tags['id'] = wait['id']
    timestamp = ' %d' % to_nanos(wait['timestamp'])
    tag_str = ','.join(['%s=%s' % (key, escape(value))
                        for key, value in sorted(tags.items())])
    value_str = ' call_duration=%f,time_offset=%f' % (wait['duration'],
                                                      wait['time_offset'])
    metrics.append('Wait,' + tag_str + value_str + timestamp)
  for verify in attempt.get('verifies', []):
    tags = dict(common_tags)
    tags['test_case'] = verify['test_case']
    tags['outcome'] = verify['outcome']
    tags['condition'] = verify['condition']
    tags['id'] = verify['id']
    timestamp = ' %d' % to_nanos(verify['timestamp'])
    tag_str = ','.join(['%s=%s' % (key, escape(value))
                        for key, value in sorted(tags.items())])
    value_str = ' call_duration=%f,time_offset=%f' % (verify['duration'],
                                                      verify['time_offset'])
    metrics.append('Verify,' + tag_str + value_str + timestamp)
  return metrics


def write_to_influx_db(url, db_name, summaries):
  """Write the extracted summaries to influxdb."""
  metrics = []
  target = url + '/write?db=%s' % db_name
  for suite in summaries:
    common_tags = {'suite': suite['suite']}
    common_tags.update(suite.get('config', {}))
    for test in suite['tests']:
      common_tags['test'] = test['name']
      for attempt in test['attempts']:
        metrics.extend(encode_attempt_metrics(attempt, common_tags))

  payload = '\n'.join(metrics)
  req = Request(url=target, data=payload)
  req.get_method = lambda: 'POST'
  urlopen(req)
  print('WROTE %d metrics to %s' % (len(metrics), target))


def main(args):
  """Program controller."""

  parser = argparse.ArgumentParser(
      description='Extract timing information from journals.')
  parser.add_argument('journals', metavar='PATH', type=str, nargs='+',
                      help='list of journals to process')
  parser.add_argument('--output_path',
                      help='path to JSON file to write extract data.')
  parser.add_argument('--influx_url',
                      help='path to influxdb to write to as CitestStats.')
  parser.add_argument('--platform',
                      help='platform the journal was produced from.')
  parser.add_argument('--branch',
                      help='branch the journal was produced from.')
  parser.add_argument('--execution_id',
                      help='execution id for test run (jenkins build number).')

  options = parser.parse_args(args)
  config_tags = {}
  if options.platform:
    config_tags['platform'] = options.platform
  if options.branch:
    config_tags['branch'] = options.branch
  if options.execution_id:
    config_tags['execution_id'] = options.execution_id

  summaries = []
  for path in options.journals:
    summaries.append(extract_times(path, config_tags))

  emit = True
  if options.output_path:
    write_to_path(options.output_path, summaries)
    emit = False

  if options.influx_url:
    write_to_influx_db(options.influx_url, 'CitestStats', summaries)
    emit = False

  if emit:
    write_to_console(summaries)


if __name__ == '__main__':
  main(sys.argv[1:])
