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


"""Converts a journaled .json file into a HTML document.

This program needs to be run with a python package defined because it uses
relative imports.

PYTHONPATH=. python -m citest.reporting.generate_html_report <test>.journal.json
"""

import os
import sys

from .html_renderer import HtmlRenderer
from .html_document_manager import HtmlDocumentManager


def journal_to_html(input_path):
  """Main program for converting a journal JSON file into HTML.

  This will write a file using in the input_path directory with the
  same basename as the JSON file, but with 'html' extension instead.

  Args:
    input_path: [string] Path the journal file.
  """
  output_path = os.path.basename(os.path.splitext(input_path)[0]) + '.html'

  document_manager = HtmlDocumentManager(title=input_path)

  document_manager.write('<table>')
  processor = HtmlRenderer(document_manager)
  processor.process(input_path)
  document_manager.write('</table>')

  document_manager.build_to_path(output_path)


if __name__ == '__main__':
  if len(sys.argv) != 2:
    sys.stderr.write('Usage: {0} <proto file>'.format(sys.argv[0]))
    sys.exit(-1)
  journal_to_html(sys.argv[1])
