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


from snapshot import (
    JsonSnapshotable,
    JsonSnapshotHelper,
    JsonSnapshot,
    Edge,
    SnapshotEntity)

from journal import Journal

# DEPRECATED(ewiseblatt): 20151214
# Scribes are deprecated by snapshoting and journaling
# however these are not yet integrated.
from scribe import(
    Doodle,
    Scribable,
    Scribe,
    ScribeClassRegistry,
    ScribeRendererSection,
    DEFAULT_SCRIBE_REGISTRY,
    DETAIL_SCRIBE_REGISTRY)

# DEPRECATED(ewiseblatt): 20151214
# Scribes are deprecated by snapshoting and journaling
# however these are not yet integrated, nor is there an HTML converter
# for journals yet.
from html_scribe import(
    HTML_SCRIBE_REGISTRY,
    HtmlScribe)

from json_scrubber import JsonScrubber
from base_test_case import BaseTestCase
from test_runner import TestRunner

from test_package import run_all_tests_in_dir
