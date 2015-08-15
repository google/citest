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


class TestBase(object):
  """Used to test renderers."""
  def __init__(self, text=None):
    self._text = text

  def __str__(self):
    return self._text


class TestDerived(TestBase):
  """Used to test class inheritence."""
  pass


class TestDefault(object):
  """Used to test global default registration."""
  pass


class ScribeTest(unittest.TestCase):
  def test_registry(self):
    registry = base.ScribeClassRegistry('Test')
    func = lambda obj, reg: 'Base'

    self.assertEqual(func, registry.find_with_default(TestBase, func).renderer)
    self.assertIsNone(registry.find_or_none(TestBase))

    registry.add(TestBase, func)
    self.assertEqual(func, registry.find_or_none(TestBase).renderer)

  def test_find_base_classes(self):
    registry = base.ScribeClassRegistry('Test')
    func = lambda obj, reg: 'Base'

    registry.add(TestBase, func)
    self.assertEqual(func, registry.find_or_none(TestDerived).renderer)

  def test_registry_inherits_from_base(self):
    func = lambda obj, reg: 'Default'
    registry = base.ScribeClassRegistry(TestDefault)
    self.assertIsNone(registry.find_or_none(TestDefault))

    base.DEFAULT_SCRIBE_REGISTRY.add(TestDefault, func)
    self.assertEqual(func, registry.find_or_none(TestDefault).renderer)

  def test_registry_spec_override(self):
    parent_func = lambda obj, reg: 'Parent'
    child_func = lambda obj, reg: 'Child'
    parent = base.scribe.ScribeClassRegistry('ParentRegistry')
    child = base.scribe.ScribeClassRegistry('ChildRegistry')

    parent.add(TestBase, parent_func)
    child.add(TestBase, child_func)

    self.assertEqual(parent_func, parent.find_or_none(TestBase).renderer)
    self.assertEqual(child_func, child.find_or_none(TestBase).renderer)

  def test_scribe_indent(self):
    scribe = base.Scribe()
    self.assertEqual('', scribe.line_indent)
    self.assertEqual(2, scribe.indent_factor)
    self.assertEqual(0, scribe.level)

    scribe.push_level()
    self.assertEqual('  ' * 1, scribe.line_indent)
    scribe.push_level()
    self.assertEqual('  ' * 2, scribe.line_indent)
    scribe.pop_level()
    self.assertEqual('  ' * 1, scribe.line_indent)
    scribe.pop_level()
    self.assertEqual('', scribe.line_indent)

  def test_scribe_render(self):
    func = lambda obj, reg: 'Hello {0}'.format(obj)
    registry = base.scribe.ScribeClassRegistry('Registry')
    registry.add(TestBase, func)

    scribe = base.Scribe(registry)
    self.assertEqual('Hello World', scribe.render(TestBase('World')))

  @staticmethod
  def push_level_and_raise_exception(obj, scribe):
    """Rendering method to inject errors."""
    scribe.push_level()
    raise ValueError('Oops')

  def test_scribe_render_exception(self):
    func = self.push_level_and_raise_exception
    registry = base.scribe.ScribeClassRegistry('Registry')
    registry.add(TestBase, func)

    scribe = base.Scribe(registry)
    # Test render errors are propagated, and level is restored.
    with self.assertRaises(ValueError):
        scribe.render(TestBase('XXX'))
    self.assertEqual(0, scribe.level)

  def test_scribe_parts(self):
    registry = base.scribe.ScribeClassRegistry('Registry')
    scribe = base.scribe.Scribe(registry)

    parts = [scribe.build_part('C', 'c'),
             scribe.build_part('A', 'a'),
             scribe.build_part('B', 'b')]
    scribe.push_level()
    self.assertEqual("C: 'c'\n  A: 'a'\n  B: 'b'", scribe.render_parts(parts))

  def test_scribe_section(self):
    registry = base.scribe.ScribeClassRegistry('Registry')
    scribe = base.scribe.Scribe(registry)

    section = scribe.make_section()
    section.parts.extend(
      [scribe.build_part('C', 'c'),
       scribe.build_part('A', 'a'),
       scribe.build_part('B', 'b')])

    parts = [scribe.build_part('Section', section)]
    self.assertEqual("Section:\n  C: 'c'\n  A: 'a'\n  B: 'b'",
                     scribe.render_parts(parts))

  def test_scribe_subsection(self):
    registry = base.scribe.ScribeClassRegistry('Registry')
    scribe = base.scribe.Scribe(registry)

    section = scribe.make_section()
    subsection = scribe.make_section()

    section.parts.extend(
      [scribe.build_part('C', 'c'),
       scribe.build_part('A', subsection),
       scribe.build_part('B', 'b')])

    subsection.parts.extend(
      [scribe.build_part('First', 1),
       scribe.build_part('Second', 2)])

    parts = [scribe.build_part('Section', section)]
    self.assertEqual("Section:\n"
                     "  C: 'c'\n"
                     "  A:\n"
                     "    First: 1\n"
                     "    Second: 2\n"
                     "  B: 'b'",
                     scribe.render_parts(parts))

  def test_scribe_list(self):
    registry = base.scribe.ScribeClassRegistry('Registry')
    registry.add(
        TestBase,
        lambda obj, scribe: 'CLASS {0}'.format(obj.__name__))
    scribe = base.scribe.Scribe(registry)

    test = ['a', TestBase, 'b']
    self.assertEqual("'a', CLASS TestBase, 'b'", scribe.render(test))

  def test_scribe_nested_list_part(self):
    registry = base.scribe.ScribeClassRegistry('Registry')
    registry.add(
        TestBase,
        lambda obj, scribe: 'CLASS {0}'.format(obj.__name__))
    scribe = base.scribe.Scribe(registry)
    test = ['a', TestBase, 'b']

    parts = [scribe.build_nested_part('Test List', test)]
    self.assertEqual("Test List:\n  'a'\n  CLASS TestBase\n  'b'",
                     scribe.render_parts(parts))

  def test_scribe_json_part(self):
    d = {'a': 'A', 'b': 'B'}
    scribe = base.scribe.Scribe()
    # The push here is to take it off the root indent to test indentation
    scribe.push_level(count=5)
    indent = scribe.line_indent
    # The pop here is because build_json_part pushes an additional level.
    # The indent reference point we just grabbed is at that inner level.
    # We pop here so that we can then push into the level of our expected indent.
    scribe.pop_level()

    part = scribe.build_json_part('Test', d)
    s = scribe.render_parts([part])
    self.assertEqual('Test:\n{indent}{{\n'
                     '{indent}  "a": "A",\n'
                     '{indent}  "b": "B"\n'
                     '{indent}}}'.format(indent=indent),
                     s)


if __name__ == '__main__':
  loader = unittest.TestLoader()
  suite = loader.loadTestsFromTestCase(ScribeTest)
  unittest.TextTestRunner(verbosity=2).run(suite)
