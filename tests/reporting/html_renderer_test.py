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

"""Test citest.reporting.html_renderer module."""

import unittest

from citest.base import (JsonSnapshotableEntity, JsonSnapshot)
from citest.reporting.html_document_manager import HtmlDocumentManager
from citest.reporting.html_renderer import HtmlRenderer
from citest.reporting.html_renderer import ProcessToRenderInfo
from citest.reporting.journal_processor import ProcessedEntityManager


class TestLinkedList(JsonSnapshotableEntity):
  # pylint: disable=missing-docstring
  # pylint: disable=too-few-public-methods
  def __init__(self, name, next_elem=None):
    self.__name = name
    self.next = next_elem

  def export_to_json_snapshot(self, snapshot, entity):
    entity.add_metadata('name', self.__name)
    if self.next:
      next_target = snapshot.make_entity_for_object(self.next)
      snapshot.edge_builder.make(entity, 'Next', next_target)


class HtmlRendererTest(unittest.TestCase):
  def test_json(self):
    """Test rendering literal json values"""
    processor = ProcessToRenderInfo(
        HtmlDocumentManager('test_json'),
        ProcessedEntityManager())
    processor.max_uncollapsable_json_lines = 20
    processor.max_uncollapsable_entity_rows = 20

    # Numeric literals wont be treated as json.
    for n in [-1, 0, 1, 3.14]:
      info = processor.process_json_html_if_possible(n)
      self.assertEquals('{0}'.format(n), info.detail_block)
      self.assertEquals(None, info.summary_block)

    # None of these strings are well-defined JSON documents
    # so should just be strings.
    for s in ['test', 'a phrase', 'True']:
      info = processor.process_json_html_if_possible(s)
      self.assertEquals("'{0}'".format(s), info.detail_block)
      self.assertEquals(None, info.summary_block)

    # Boolean values wont be considered JSON.
    for b in [True, False]:
      info = processor.process_json_html_if_possible(b)
      self.assertEquals('{0}'.format(str(b)), info.detail_block)
      self.assertEquals(None, info.summary_block)

    # Dictionaries and JSON dictionary strings normalize to JSON.
    for d in [{'A': 'a', 'B': True}, '{"A":"a", "B":true}']:
      info = processor.process_json_html_if_possible(d)
      self.assertEquals('<pre>{"A":"a","B":true}</pre>',
                        str(info.detail_block).replace(' ', ''))
      self.assertEquals(None, info.summary_block)
      self.assertEquals(None, info.summary_block)

    # Lists and JSON lists strings normalize to JSON.
    for l in [[123, 'abc', True, {'A': 'a', 'B': 'b'}],
              '[123, "abc", true, {"A":"a", "B":"b"}]']:
      info = processor.process_json_html_if_possible(l)
      self.assertEquals(
          '<pre>[123,"abc",true,{"A":"a","B":"b"}]</pre>',
          str(info.detail_block).replace(' ', ''))
      self.assertEquals(None, info.summary_block)

  def test_expandable_tag_attrs(self):
    """Test the production of HTML tag decorators controling show/hide."""
    manager = HtmlDocumentManager('test_json')

    section_id = 'SID'

    # Test block both as being initially expanded then not.
    detail_tags, summary_tags = manager.make_expandable_tag_attr_kwargs_pair(
        section_id, default_expanded=True)
    self.assertEqual({'id': 'SID.1'}, detail_tags)
    self.assertEqual({'id': 'SID.0', 'style': 'display:none'}, summary_tags)

    detail_tags, summary_tags = manager.make_expandable_tag_attr_kwargs_pair(
        section_id, default_expanded=False)
    self.assertEqual({'id': 'SID.1', 'style': 'display:none'}, detail_tags)
    self.assertEqual({'id': 'SID.0'}, summary_tags)

  def test_expandable_control(self):
    """Test the production of HTML controller for show/hide."""
    manager = HtmlDocumentManager('test_json')

    # Test block both as being initially expanded then not.
    tag = manager.make_expandable_control_tag('SID', 'TEST')
    self.assertEqual(
        '<a class="toggle" onclick="toggle_inline(\'SID\');">TEST</a>',
        str(tag))

  def test_process_snapshot(self):
    """Test the conversion of a snapshot into HTML."""
    tail = TestLinkedList(name='tail')
    head = TestLinkedList(name='head', next_elem=tail)
    snapshot = JsonSnapshot()
    snapshot.make_entity_for_object(head)
    json_snapshot = snapshot.to_json_object()

    entity_manager = ProcessedEntityManager()
    processor = ProcessToRenderInfo(
        HtmlDocumentManager('test_json'), entity_manager)
    processor.max_uncollapsable_json_lines = 20
    processor.max_uncollapsable_metadata_rows = 20
    processor.max_uncollapsable_entity_rows = 20
    processor.default_force_top_level_collapse = False

    entity_manager.push_entity_map(json_snapshot['_entities'])
    html_info = processor.process_entity_id(json_snapshot['_subject_id'],
                                            json_snapshot)
    entity_manager.pop_entity_map(json_snapshot['_entities'])

    expect = """<table>
  <tr>
    <th><i>metadata</i></th>
    <td>
      <table>
        <tr><th>_id</th><td>1</td></tr>
        <tr><th>class</th><td>type TestLinkedList</td></tr>
        <tr><th>name</th><td>head</td></tr>
      </table>
    </td>
  </tr>
  <tr>
    <th>Next</th>
    <td>
      <table>
        <tr>
          <th><i>metadata</i></th>
          <td>
            <table>
              <tr><th>_id</th><td>2</td></tr>
              <tr><th>class</th><td>type TestLinkedList</td></tr>
              <tr><th>name</th><td>tail</td></tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
"""
    # Test without regard to whitespace formatting.
    self.assertEquals(''.join(expect.split()),
                      ''.join(str(html_info.detail_block).split()))

  def test_cycle(self):
    tail = TestLinkedList(name='tail')
    head = TestLinkedList(name='head', next_elem=tail)
    tail.next = head
    snapshot = JsonSnapshot()

    entity_manager = ProcessedEntityManager()
    processor = ProcessToRenderInfo(
        HtmlDocumentManager('test_json'), entity_manager)

    snapshot.make_entity_for_object(head)
    json_snapshot = snapshot.to_json_object()
    self.assertEqual(1, json_snapshot.get('_subject_id'))
    entity_manager.push_entity_map(json_snapshot.get('_entities'))
    info = processor.process_entity_id(1, snapshot)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(HtmlRendererTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
