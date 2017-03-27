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


"""The reporting package is responsible for processing data from test journals.

The test journals capture runtime information from test execution. These are
then post processed to get useful metrics or viewpoints out of rather than
making these intrinsic to the execution itself. That way you can decide later
the abstractions to use for the type of debugging or comparative reference you
want to perform.
"""

# The navigator module provides simple traversal of journal files.
# It doesnt provide any interpretation or extraction, but it does understand
# the journal file format.
from .journal_navigator import JournalNavigator

# The processor provides a base class for providing handlers on different types
# of journal entries. It doesnt do anything interesting, but provides
# boilerplate code so that specific renderers or processors can focus on their
# task at hand and not infrastructure.
from .journal_processor import (
    JournalProcessor,
    ProcessedEntityManager)

# The HTML document manager provides support for producing HTML documents.
from .html_document_manager import HtmlDocumentManager

# The HTML renderer translates journal entries into HTML fragments that
# can be placed into HTML documents using the html_document_manager.
from .html_renderer import HtmlRenderer

# The Dump renderer translates journal entries into text fragments that
# are meant to support debugging journal entries as opposed to reading
# them to debug tests (in a TextRenderer).
from .dump_renderer import DumpRenderer

# Top level function for converting a journal into HTML.
from .generate_html_report import journal_to_html
