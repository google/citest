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

import unittest
import citest.base as base


class TestObject(base.Scribable):
  @property
  def value(self):
    return self._value

  def __init__(self, value):
    self._value = value

  def _make_scribe_parts(self, scribe):
    return [scribe.build_part('Value', self._value)]


def test_obj_to_html(obj):
    return """<table>
  <tr><th>CLASS</th><td>
  TestObject</td>
  <tr><th>Value</th><td>
  {0}</td>
</table>""".format(obj.value)


def test_obj_list_to_html(l):
  # Build a list of html strings where
  # each element of the list is the rendering of a line item.
  # The line item is indented a scope level, and indents the
  # corresponding html element another level since it contains it.
  html = []
  for e in l:
    elem_html = test_obj_to_html(e)
    html.append('\n  <li> {0}'.format(elem_html.replace('\n', '\n  ')))

  # Wrap the element html into UL tags.
  return '<ul>{0}\n</ul>'.format(''.join(html))


class HtmlScribeTest(unittest.TestCase):
  def test_string(self):
      scribe = base.html_scribe.HtmlScribe()
      text = scribe.render('Hello, World!')
      self.assertEqual('Hello, World!', text)

  def test_simple_object(self):
      obj = TestObject('Hello, World!')
      scribe = base.html_scribe.HtmlScribe()
      text = scribe.render(obj)
      self.assertEqual(test_obj_to_html(obj), text)

  def test_object_list(self):
      l = [ TestObject('A'), TestObject('B') ]
      scribe = base.html_scribe.HtmlScribe()
      text = scribe.render(l)
      self.assertEqual(test_obj_list_to_html(l), text)

  def test_list_of_list(self):
      innerAB = [ TestObject('A'), TestObject('B') ]
      innerXY = [ TestObject('X'), TestObject('Y') ]
      outer = [innerAB, innerXY]
      scribe = base.html_scribe.HtmlScribe()
      text = scribe.render(outer)
      # Inner HTML will be indented an extra level
      innerAB_html = test_obj_list_to_html(innerAB).replace('\n', '\n  ')
      innerXY_html = test_obj_list_to_html(innerXY).replace('\n', '\n  ')
      self.assertEqual('<ul>\n  <li> {0}\n  <li> {1}\n</ul>'.format(
          innerAB_html, innerXY_html), text)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(HtmlScribeTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
