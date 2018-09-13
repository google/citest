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

"""Helper classes and methods for rendering an HTML index entry for a journal.
"""

import os
import sys
from citest.base import (JournalProcessor, ProcessedEntityManager)


class HtmlIndexRenderer(JournalProcessor):
  """Specialized JournalProcessor to produce HTML index pages."""

  def __init__(self, document_manager):
    """Constructor.

    Args:
      document_manager: [HtmlDocumentManager] Helps with look & feel,
          and structure.
    """
    super(HtmlIndexRenderer, self).__init__()
    self.__document_manager = document_manager
    self.default_handler = self.__handle_generic
    self.__total_passed = 0
    self.__total_failed = 0
    self.__total_secs = 0
    self.__overall_status = None

    self.__first_timestamp = None
    self.__last_timestamp = None
    self.__passed_count = 0
    self.__failed_count = 0
    self.__depth = 0
    self.__in_test = False
    self.__summary_status = None

  def __reset_journal_counters(self):
    self.__overall_status = self.__ingest_summary_status(
        self.__overall_status, self.__summary_status)
    self.__first_timestamp = None
    self.__last_timestamp = None
    self.__passed_count = 0
    self.__failed_count = 0
    self.__depth = 0
    self.__in_test = False
    self.__summary_status = None

  def __ingest_summary_status(self, baseline, hint):
    """Add hint for overall status."""
    sequence = [None, 'VALID', 'INVALID', 'ERROR']

    hint_index = sequence.index(hint)
    if hint_index < 0:
      raise ValueError('Unhandled hint {0}'.format(hint))
    return hint if hint_index > sequence.index(baseline) else baseline

  def __increment_relation_count(self, relation):
    """Increment number of relations."""
    self.__summary_status = self.__ingest_summary_status(
        self.__summary_status, relation)
    if relation == 'VALID':
      self.__passed_count += 1
    elif relation == 'INVALID':
      self.__failed_count += 1
    elif relation == 'ERROR':
      self.__failed_count += 1
    else:
      raise ValueError('Unhandled relation {0}'.format(relation))

  def __handle_generic(self, entry):
    """Handles entries from the journal to update the overall summary.

    Args:
      entry: JSON entry from the journal
    """
    # Update our running timestamps bounding overall processing time.
    timestamp = entry.get('_timestamp')
    if self.__first_timestamp is None:
      self.__first_timestamp = timestamp
    self.__last_timestamp = timestamp or self.__last_timestamp

    if entry.get('_type') == 'JsonSnapshot' and self.__depth == 0:
      # Consider root-level snapshots for overall status.
      entity_manager = ProcessedEntityManager()
      entity_manager.push_entity_map(entry.get('_entities', {}))
      relation = entity_manager.lookup_entity_with_id(
          entry.get('_subject_id')).get('_default_relation')
      self.__summary_status = self.__ingest_summary_status(
          self.__summary_status, relation)
      return

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
           self.__in_test = entry.get('_title', '').startswith('Test ')
        return

    if entry.get('control') == 'END':
        # pylint: disable=bad-indentation
        self.__depth -= 1
        if self.__depth == 0 and self.__in_test:
          relation = entry.get('relation')
          self.__increment_relation_count(relation)
        return

  @property
  def output_column_names(self):
    """Returns list of column names for the summary table."""
    return ['P', 'F', 'Test Module', 'Time']

  def process(self, journal):
    """Overrides JournalProcessor.process() for an individual journal.

    When we process a journal, we're going to reduce it down to a summary
    line in our index that links to the journal output.
    We're also going to accumulate overall statistics for the index summary.

    Args:
      journal: [string] The path to the journal file to process.
    """
    self.__reset_journal_counters()
    super(HtmlIndexRenderer, self).process(journal)

    if self.__passed_count == 0 and self.__failed_count == 0:
      sys.stderr.write(
          'No tests recorded in {0}. Assuming this is an error.\n'.format(
              journal))
      self.__failed_count = 1

    journal_basename = os.path.basename(journal)
    if journal_basename.endswith('.journal'):
      journal_basename = os.path.splitext(journal_basename)[0]
    html_path = os.path.splitext(journal)[0] + '.html'

    self.__total_passed += self.__passed_count
    self.__total_failed += self.__failed_count

    if self.__last_timestamp is not None:
      secs = self.__last_timestamp - self.__first_timestamp
      self.__total_secs += secs
    else:
      secs = None

    summary = self.__document_manager.make_tag_text(
        'a', journal_basename, class_='toggle', href=html_path)
    self.__write_row(self.__passed_count, self.__failed_count, summary, secs,
                     self.__summary_status)

  def __write_row(self, passed_count, failed_count, summary, secs,
                  summary_status):
    """Helper function to write an individual row in the index."""
    pcss = {}
    css = {}

    _, fcss = self.__document_manager.determine_attribute_css_kwargs(
        summary_status)

    if passed_count > 0:
      pcss = {'class_': 'valid'}  # It's always good something passed.
      css = pcss               # Assume overall success is good

    if failed_count > 0:
      css = fcss               # Overall success is bad if something failed.

    if secs is not None:
      time = '' if secs < 3600 else '%d:' % (secs // 3600)
      secs %= 3600
      time += '%02d:%02d secs' % (secs // 60, secs % 60)
    else:
      time = 'Unknown'

    document_manager = self.__document_manager
    document_manager.append_tag(
        document_manager.make_tag_container('tr', [
            document_manager.make_tag_text('td', str(passed_count), **pcss),
            document_manager.make_tag_text('td', str(failed_count), **fcss),
            document_manager.make_tag_container('td', [summary], **css),
            document_manager.make_tag_text('td', time)
            ]))

  def terminate(self):
    """Implements interface for JournalProcessor.

    This terminates the index after the last journal has been processed.
    """
    # Write a little separator
    document_manager = self.__document_manager
    document_manager.append_tag(
        document_manager.make_tag_container('tr', [
            document_manager.new_tag('td', colspan=5,
                                     style='background-color:#999999')]))

    # Add the summary row
    self.__write_row(self.__total_passed, self.__total_failed,
                     "<em>Overall Total</em>", self.__total_secs,
                     self.__overall_status)
