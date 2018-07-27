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

"""Helper classes and methods for rendering a table of results where
each row is a test and each column is a different occurance of it.
"""

import os
import sys
from .journal_processor import JournalProcessor
from .html_document_manager import HtmlDocumentManager

class TestStats(object):
  """Statistics for a test."""
  @staticmethod
  def new():
    """Return a new empty instance."""
    return TestStats(0, 0, 0, 0)

  @property
  def count(self):
    """Return the number of tests recorded."""
    return self.passed + self.failed + self.error

  @property
  def homogeneous(self):
    """True if all the tests have the same final outcome."""
    if self.error:
      return self.failed + self.passed == 0
    if self.failed:
      return self.passed == 0
    return True

  @property
  def result_name(self):
    """Overall Passed/Failed/Error status."""
    if self.error:
      return 'Error'
    if self.failed:
      return 'Failed'
    if self.passed:
      return 'Passed'
    return 'Nothing'

  def __init__(self, passed, failed, error, secs):
    self.passed = passed
    self.failed = failed
    self.error = error
    self.secs = secs

  def aggregate(self, stats):
    """Sum stats."""
    self.passed += stats.passed
    self.failed += stats.failed
    self.error += stats.error
    self.secs += stats.secs

  def determine_css(self, suffix=''):
    """Determine CSS style to use for the overall status."""
    if self.error:
      return {'class_': 'error' + suffix}
    if self.failed:
      return {'class_': 'invalid' + suffix}
    if self.passed:
      return {'class_': 'valid' + suffix}
    return {}

  def to_text(self):
    """Return the text summary of the status counts."""
    if self.count == 0:
      return 'No Tests Ran'
    if self.count == 1:
      return self.result_name.upper()
    if self.homogeneous:
      return '%s ALL %d' % (self.result_name, self.count)
    if self.error:
      return '%s %d+%d of %d' % (
          self.result_name, self.error, self.failed, self.count)

    return '%s %d of %d' % (self.result_name, self.failed, self.count)


def make_directory_shortname_map(dir_paths):
  """Given a collection of directory paths, produce a shorter name for each one.

  The shortened name will be just the components of each name that are unique.
  Common relative path parts will be eliminated.
  """
  if not dir_paths:
    return {}

  path_to_parts = {path : path.split('/') for path in dir_paths}
  all_path_parts = path_to_parts.values()
  first = all_path_parts[0]

  def match_position(index, expect):
    """Determine if the path part at index is the expected value."""
    for path in all_path_parts:
      if len(path) <= index or path[index] != expect:
        return False
    return True

  index = 0
  while index < len(first):
    if match_position(index, first[index]):
      for path in all_path_parts:
        del path[index]
    else:
      index += 1
  return {path : '/'.join(path_to_parts[path]) for path in dir_paths}


class HtmlIndexTableRenderer(JournalProcessor):
  """Specialized JournalProcessor to produce HTML index table pages."""

  @staticmethod
  def write_test_summary_tables(
      journal_to_details, dir_to_column_name, output_dir):
    """Write the summary tables for each test suite.

    The test suite summary has a row for each test in the suite
    and a column for each execution of that test. These are written
    as test_name + '_index.html'

    Args:
      journal_to_details: [map of map of TestStats]
         Keyed by journal, the value is the stats for each of the tests
         in that journal, keyed by the name of the test
      dir_to_column_name: [map of dirname to column name]
         identifies the different test runs
      output_dir: [path] Path to directory to write summary tables.
    """
    unique_basenames = set([])
    for path in journal_to_details.keys():
      unique_basenames.add(os.path.basename(path))

    for basename in unique_basenames:
      HtmlIndexTableRenderer.write_test_summary_for_basename(
          basename, journal_to_details, dir_to_column_name, output_dir)

  @staticmethod
  def write_test_summary_for_basename(
      basename, journal_to_details, dir_to_column_name, output_dir):
    """Writes the summary file for an individual test suite.

    Each journal that ran a test in the suite will have a column, however
    journals that ran no tests in the suite will not be present.
    If a journal did not run a test that another test wrote, its cell for
    that row will be empty.
    """
    document_manager = HtmlDocumentManager(
        'Summary for %s' % os.path.splitext(basename)[0])
    processor = HtmlIndexTableRenderer(document_manager)
    html_filename = os.path.splitext(basename)[0] + '.html'
    all_test_names = set([])
    dirname_stats = {}
    column_keys = sorted(dir_to_column_name.keys())
    for dirname in column_keys:
      dirname_stats[dirname] = TestStats.new()
      details = journal_to_details.get(os.path.join(dirname, basename))
      if not details:
        continue
      all_test_names.update(details.keys())

    header_cols = [document_manager.make_tag_text('th', '')]
    header_cols.extend(
        [document_manager.make_tag_container(
            'th',
            [document_manager.make_tag_text(
                'a', dir_to_column_name[path],
                href=os.path.join(path, 'index.html'))],
            class_='toggle')
         for path in column_keys])
    header_cols.append(document_manager.make_tag_text('th', 'Summary'))
    header_tr_tag = document_manager.make_tag_container('tr', header_cols)

    # Write a row into the table for a given test case.
    table_rows = [header_tr_tag]
    for test_name in sorted(list(all_test_names)):
      row_stats = TestStats.new()
      row = [
          document_manager.make_tag_html(
              'th',
              document_manager.make_tag_text('a', test_name, class_='toggle'))
        ]
      for dirname in column_keys:
        details = journal_to_details.get(os.path.join(dirname, basename))
        if not details or test_name not in details:
          row.append(document_manager.make_tag_text('td', ''))
          continue
        stats = details[test_name]
        row_stats.aggregate(stats)
        dirname_stats[dirname].aggregate(stats)
        html_path = os.path.join(dirname, html_filename)
        cell_summary = processor.make_summary_cell(html_path, stats, suffix='')
        row.append(document_manager.make_tag_container('td', [cell_summary]))

      # Write summary column at the end that summarizes the row
      row_summary = processor.make_summary_cell(None, row_stats, suffix='I')
      row.append(document_manager.make_tag_container('td', [row_summary]))
      table_rows.append(document_manager.make_tag_container('tr', row))

    # Write summary row at the bottom that sumarizes each column.
    row = [document_manager.make_tag_text('th', 'Summary')]
    total_stats = TestStats.new()
    for dirname in column_keys:
      stats = dirname_stats[dirname]
      total_stats.aggregate(stats)
      column_index_path = os.path.join(dirname, html_filename)
      column_summary = processor.make_summary_cell(
          column_index_path, stats, 'I')
      row.append(document_manager.make_tag_container(
          'td', [column_summary]))

    column_summary = processor.make_summary_cell(None, total_stats, 'I')
    row.append(document_manager.make_tag_container('td', [column_summary]))
    table_rows.append(document_manager.make_tag_container('tr', row))

    table = document_manager.make_tag_container(
        'table', table_rows, style='font-size:10pt')
    document_manager.append_tag(table)
    document_manager.build_to_path(
        os.path.join(output_dir, os.path.splitext(basename)[0] + '_index.html'))

  @staticmethod
  def process_all(document_manager, journal_list, output_dir):
    """Process all the journals and write out summary tables.

    Args:
      journal_list: [list of paths] Paths to journal files to tabulate.
      output_dir: [path] Directory for table html files.
    """
    dirs = set([os.path.dirname(path) for path in journal_list])
    file_names = set([os.path.basename(path) for path in journal_list])
    dir_to_column_name = make_directory_shortname_map(dirs)
    journal_to_cell = {}
    journal_to_stats = {}
    journal_to_details = {}

    column_keys = sorted(dir_to_column_name.keys())
    column_stats = {key: TestStats.new() for key in column_keys}
    row_stats = {key: TestStats.new() for key in file_names}

    processor = HtmlIndexTableRenderer(document_manager)

    # Process all the journals to get the stats that we're going
    # to render into the table cells.
    for journal in sorted(journal_list):
      summary, stats, details = processor.process(journal)
      journal_to_cell[journal] = summary
      journal_to_stats[journal] = stats
      journal_to_details[journal] = details
      row_stats[os.path.basename(journal)].aggregate(stats)
      column_stats[os.path.dirname(journal)].aggregate(stats)
    processor.terminate()

    HtmlIndexTableRenderer.write_test_summary_tables(
        journal_to_details, dir_to_column_name, output_dir)

    header_cols = [document_manager.make_tag_text('th', '')]
    header_cols.extend(
        [document_manager.make_tag_container(
            'th',
            [document_manager.make_tag_text(
                'a', dir_to_column_name[path],
                href=os.path.join(path, 'index.html'))],
            class_='toggle')
         for path in column_keys])
    header_cols.append(document_manager.make_tag_text('th', 'Summary'))
    header_tr_tag = document_manager.make_tag_container('tr', header_cols)

    # Write a row into the table for a given test case.
    table_rows = [header_tr_tag]
    for test_name in sorted(file_names):
      test_basename = os.path.splitext(test_name)[0]
      test_summary_path = test_basename + '_index.html'
      row = [
          document_manager.make_tag_container(
              'th',
              [document_manager.make_tag_text(
                  'a', test_basename,
                  href=test_summary_path,
                  class_='toggle')])]

      for path in column_keys:
        source = os.path.join(path, test_name)
        if source in journal_list:
          source_dir = os.path.dirname(source)
          journal_file = os.path.join(source_dir, test_basename + '.journal')
          cell_html = journal_to_cell[journal_file]
          row.append(document_manager.make_tag_container('td', [cell_html]))
        else:
          row.append(document_manager.make_tag_container('td', []))

      # Write summary column at the end that summarizes the row
      row_summary = processor.make_summary_cell(
          test_summary_path, row_stats[test_name], suffix='I')
      row.append(document_manager.make_tag_container('td', [row_summary]))
      table_rows.append(document_manager.make_tag_container('tr', row))

    # Write summary row at the bottom that sumarizes each column.
    row = [document_manager.make_tag_text('th', 'Summary')]
    total_stats = TestStats.new()
    for path in column_keys:
      stats = column_stats[path]
      total_stats.aggregate(stats)
      column_index_path = os.path.join(path, 'index.html')
      column_summary = processor.make_summary_cell(
          column_index_path, stats, 'I')
      row.append(
          document_manager.make_tag_container('td', [column_summary]))

    column_summary = processor.make_summary_cell(None, total_stats, 'I')
    row.append(document_manager.make_tag_container('td', [column_summary]))
    table_rows.append(document_manager.make_tag_container('tr', row))

    table = document_manager.make_tag_container(
        'table', table_rows, style='font-size:10pt')
    document_manager.append_tag(table)

  def __init__(self, document_manager):
    """Constructor.

    Args:
      document_manager: [HtmlDocumentManager] Helps with look & feel,
          and structure.
    """
    super(HtmlIndexTableRenderer, self).__init__()
    self.__document_manager = document_manager
    self.default_handler = self.__handle_generic
    self.__total_stats = TestStats.new()

    self.__stats = TestStats.new()
    self.__depth = 0
    self.__detail_stats = {}
    self.__start_timestamp = None
    self.__in_test = None

  def __reset_journal_counters(self):
    self.__stats = TestStats.new()
    self.__depth = 0
    self.__detail_stats = {}
    self.__start_timestamp = None
    self.__in_test = None

  def __handle_generic(self, entry):
    """Handles entries from the journal to update the overall summary.

    Args:
      entry: JSON entry from the journal
    """
    # Look for top-level control objects that indicate tests.
    # TODO(ewiseblatt): 20160301
    # This should be formalized since the concept of a test is reasonably
    # primitive. Maybe specialize the control by citing the name of the test
    # in an attribute whose semantics indicate the context block for a test.
    if entry.get('_type') != 'JournalContextControl':
      return

    if entry.get('control') == 'BEGIN':
        # pylint: disable=bad-indentation
        self.__depth += 1
        if self.__depth == 1:
           self.__in_test = entry.get('_title', '')
           if not self.__in_test.startswith('Test '):
             self.__in_test = None
           self.__start_timestamp = entry.get('_timestamp')
        return

    if entry.get('control') == 'END':
        # pylint: disable=bad-indentation
        self.__depth -= 1
        if self.__depth == 0 and self.__in_test:
          passed = 0
          failed = 0
          error = 0
          end_timestamp = entry.get('_timestamp')
          secs = (end_timestamp - self.__start_timestamp
                  if end_timestamp and self.__start_timestamp
                  else 0)
          relation = entry.get('relation')
          if relation == 'VALID':
            passed = 1
          elif relation == 'INVALID':
            failed = 1
          elif relation == 'ERROR':
            error = 1
          else:
            raise ValueError('Unhandled relation {0}'.format(relation))

          test_stats = TestStats(passed, failed, error, secs)
          self.__stats.aggregate(test_stats)
          if self.__in_test:
            self.__detail_stats[self.__in_test] = test_stats
            self.__in_test = None
        return

  def process(self, journal):
    self.__reset_journal_counters()

    super(HtmlIndexTableRenderer, self).process(journal)

    if self.__stats.count == 0:
      sys.stderr.write(
          'No tests recorded in {0}. Assuming this is an error.\n'.format(
              journal))
      self.__stats.error = 1

    journal_basename = os.path.basename(journal)
    if journal_basename.endswith('.journal'):
      journal_basename = os.path.splitext(journal_basename)[0]
    html_path = os.path.splitext(journal)[0] + '.html'
    self.__total_stats.aggregate(self.__stats)

    cell_html = self.make_summary_cell(html_path, self.__stats)

    return cell_html, self.__stats, self.__detail_stats

  def make_summary_cell(self, html_path, stats, suffix=''):
    """Helper function to write an individual row in the index."""
    secs = stats.secs
    if secs is not None:
      time = '' if stats.secs < 3600 else '%d:' % (secs // 3600)
      secs %= 3600
      time += '%02d:%02d secs' % (secs // 60, secs % 60)
    else:
      time = 'Unknown'

    document_manager = self.__document_manager
    detail = document_manager.make_tag_html(
        'div',
        '%s<br/>%s' % (stats.to_text(), time),
        **stats.determine_css(suffix=suffix))

    if html_path:
      summary = document_manager.make_tag_container(
          'a', [detail], class_='toggle', href=html_path)
    else:
      summary = detail

    return summary
