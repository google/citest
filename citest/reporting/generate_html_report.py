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


"""Converts citest journals into HTML documents.

This program needs to be run with a python package defined because it uses
relative imports.

PYTHONPATH=. python -m citest.reporting.generate_html_report <test>.journal

If invoked with multiple journals, it will render a separate HTML file for
each, and an "index.html" that is an overall summary of all the individual
files.

To only generate an index file, invoke with --nohtml.
To only generate the HTML files, invoke with --noindex.
"""

import argparse
import os
import resource
import sys

from citest.reporting.html_renderer import HtmlRenderer
from citest.reporting.html_document_manager import HtmlDocumentManager
from citest.reporting.html_index_renderer import HtmlIndexRenderer
from citest.reporting.html_index_table_renderer import HtmlIndexTableRenderer


def journal_to_html(input_path, prune=False):
  """Main program for converting a journal JSON file into HTML.

  This will write a file using in the input_path directory with the
  same basename as the JSON file, but with 'html' extension instead.

  Args:
    input_path: [string] Path the journal file.
  """
  output_path = os.path.basename(os.path.splitext(input_path)[0]) + '.html'

  document_manager = HtmlDocumentManager(
      title='Report for {0}'.format(os.path.basename(input_path)))

  processor = HtmlRenderer(document_manager, prune=prune)
  processor.process(input_path)
  processor.terminate()
  document_manager.wrap_tag(document_manager.new_tag('table'))
  document_manager.build_to_path(output_path)


def determine_columns(dir_names):
  if not dir_names:
    return []

  path_to_parts = {path : path.split('/') for path in dir_names}
  all_path_parts = path_to_parts.values()
  first = all_path_parts[0]

  def match_position(index, expect):
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
  return {name : '/'.join(path_to_parts[name]) for name in dir_names}


def build_table(journal_list, output_dir):
  document_manager = HtmlDocumentManager(title='Journal Summary')
  document_manager.has_key = False
  document_manager.has_global_expand = False

  HtmlIndexTableRenderer.process_all(document_manager, journal_list, output_dir)
  document_manager.build_to_path(os.path.join(output_dir, 'table_index.html'))

  
def build_index(journal_list, output_dir):
  """Create an index.html file for HTML output from journal list.

  Args:
    journal_list: [array of path] Path to the journal files to put in the index.
       Assumes that there is a corresponding .html file for each to link to.
  """
  document_manager = HtmlDocumentManager(title='Journal Summary')
  document_manager.has_key = False
  document_manager.has_global_expand = False

  processor = HtmlIndexRenderer(document_manager)
  for journal in journal_list:
    processor.process(journal)
  processor.terminate()

  tr_tag = document_manager.make_tag_container(
      'tr',
      [document_manager.make_tag_text('th', name)
       for name in processor.output_column_names])
  table = document_manager.make_tag_container(
      'table', [tr_tag], style='font-size:12pt')
  document_manager.wrap_tag(table)

  document_manager.build_to_path(os.path.join(output_dir, 'index.html'))


def main(argv):
  """Main program execution.

  Args:
    argv: [array of string]  The command line arguments
  """
  if len(argv) == 1:
    sys.stderr.write('Usage: {0} <journal file>+'.format(argv[0]))
    sys.exit(-1)

  parser = argparse.ArgumentParser()
  parser.add_argument('journals', metavar='PATH', type=str, nargs='+',
                      help='list of journals to process')
  parser.add_argument('--table', default=False, action='store_true',
                      help='Build a table where each unique filename is a row'
                      ' and each directory with a journal file is a column.'
                      ' The cells are the journal filename for that directory.')
  parser.add_argument('--index', default=True, action='store_true',
                      help='Generate an index.html from all the journals.')
  parser.add_argument('--noindex', dest='index', action='store_false',
                      help='Generate an index.html from all the journals.')
  parser.add_argument('--html', default=True, action='store_true',
                      help='Generate HTML report for each journal.')
  parser.add_argument('--nohtml', dest='html', action='store_false',
                      help='Do not genreate an HTML report for the journals.')
  parser.add_argument('--show_memory', default=False, action='store_true',
                      help='Show how much memory we needed.')
  parser.add_argument('--prune_html', default=False, action='store_true',
                      help='Prune resulting HTML to make it more concise for'
                      ' typical verification and debugging use cases.')
  parser.add_argument('--output_dir', default='.',
                      help='Write index files to this base directory')

  options = parser.parse_args(argv[1:])

  if options.html:
    for path in options.journals:
      journal_to_html(path, prune=options.prune_html)

  if options.table:
    build_table(options.journals, options.output_dir)

  if options.index and len(options.journals) > 1:
    build_index(options.journals, options.output_dir)

  if options.show_memory:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    print 'Memory Usage (RSS): %dMiB' % (usage.ru_maxrss / (1024 * 1024))


if __name__ == '__main__':
  main(sys.argv)
