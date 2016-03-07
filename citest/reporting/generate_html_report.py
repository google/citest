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
import sys

from .html_renderer import HtmlRenderer
from .html_document_manager import HtmlDocumentManager
from .html_index_renderer import HtmlIndexRenderer


def journal_to_html(input_path):
  """Main program for converting a journal JSON file into HTML.

  This will write a file using in the input_path directory with the
  same basename as the JSON file, but with 'html' extension instead.

  Args:
    input_path: [string] Path the journal file.
  """
  output_path = os.path.basename(os.path.splitext(input_path)[0]) + '.html'

  document_manager = HtmlDocumentManager(
      title='Report for {0}'.format(os.path.basename(input_path)))

  document_manager.write('<table>')
  processor = HtmlRenderer(document_manager)
  processor.process(input_path)
  processor.terminate()
  document_manager.write('</table>')

  document_manager.build_to_path(output_path)


def build_index(journal_list):
  """Create an index.html file for HTML output from journal list.

  Args:
    journal_list: [array of path] Path to the journal files to put in the index.
       Assumes that there is a corresponding .html file for each to link to.
  """
  document_manager = HtmlDocumentManager(title='Journal Summary')
  document_manager.has_key = False
  document_manager.has_global_expand = False

  processor = HtmlIndexRenderer(document_manager)
  document_manager.write('<table style="font-size:12pt">')
  document_manager.write('\n<tr>\n  <th>{0}\n'.format(
      '<th>'.join(processor.output_column_names)))

  for journal in journal_list:
    processor.process(journal)
  processor.terminate()

  document_manager.write('</table>')
  document_manager.build_to_path('index.html')


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
  parser.add_argument('--index', default=True, action='store_true',
                      help='Generate an index.html from all the journals.')
  parser.add_argument('--noindex', dest='index', action='store_false',
                      help='Generate an index.html from all the journals.')
  parser.add_argument('--html', default=True, action='store_true',
                      help='Generate HTML report for each journal.')
  parser.add_argument('--nohtml', dest='html', action='store_false',
                      help='Do not genreate an HTML report for the journals.')

  options = parser.parse_args()

  if options.html:
    for path in options.journals:
      journal_to_html(path)

  if options.index and len(options.journals) > 1:
    build_index(options.journals)


if __name__ == '__main__':
  main(sys.argv)
