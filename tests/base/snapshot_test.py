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


"""Test snapshot module."""
# pylint: disable=missing-docstring
# pylint: disable=too-few-public-methods
# pylint: disable=invalid-name

import unittest

from citest.base import (
    JsonSnapshot,
    JsonSnapshotable,
    JsonSnapshotableEntity,
    JsonSnapshotHelper)


class TestWrappedValue(JsonSnapshotable):
  @property
  def value(self):
    return self.__value

  def __init__(self, value):
    self.__value = value

  def __eq__(self, other):
    return self.__class__ == other.__class__ and self.__value == other.value

  def to_snapshot_value(self, snapshot):
    return self.__value


class TestLinkedList(JsonSnapshotableEntity):
  def __init__(self, name, next_elem=None):
    self.__name = name
    self.next = next_elem

  def export_to_json_snapshot(self, snapshot, entity):
    entity.add_metadata('name', self.__name)
    if self.next:
      next_target = snapshot.make_entity_for_object(self.next)
      snapshot.edge_builder.make(entity, 'Next', next_target)


class TestSpecializedLinkedList(TestLinkedList):
  pass


class SnapshotTest(unittest.TestCase):
  def assertItemsEqual(self, a, b):
    """See if items are equal independent of sort order."""
    self.assertEquals(sorted(a), sorted(b))

  def test_assert_expected_value_ok(self):
    tests = [
        (False, False),
        (1, 1),
        ('a', 'a'),
        (3.14, 3.14),
        ([1, 'a'], [1, 'a']),
        ({'a': 'A', 'b': 'B'}, {'b': 'B', 'a': 'A'}),
        (TestLinkedList('A', TestLinkedList('B')),
         TestLinkedList('A', TestLinkedList('B'))),
        (None, None),
        (dict.__class__, dict.__class__)]
    for spec in tests:
      JsonSnapshotHelper.AssertExpectedValue(spec[0], spec[1])

    tests = [
        (False, True),
        (1, 2),
        ('a', 'b'),
        (3.14, -3.14),
        ([1, 'a'], ['a', 1]),
        ([1, 'a'], [1, 'a', 2]),
        ({'a': 'A', 'b': 'B'}, {'a': 'A', 'b': 'B', 'c': 'C'}),
        (TestLinkedList('A', TestLinkedList('B')),
         TestLinkedList('A', TestLinkedList('C'))),
        (None, False),
        (dict, dict.__class__)]
    for spec in tests:
      self.assertRaises(
          AssertionError,
          JsonSnapshotHelper.AssertExpectedValue, spec[0], spec[1])

  def test_to_json_snapshot_value(self):
    """Test conversion of values."""
    snapshot = JsonSnapshot()

    # Primitive types dont affect snapshot.
    self.assertEquals(2, JsonSnapshotHelper.ToJsonSnapshotValue(2, snapshot))
    self.assertEquals(
        2.0, JsonSnapshotHelper.ToJsonSnapshotValue(2.0, snapshot))
    self.assertEquals(
        '2', JsonSnapshotHelper.ToJsonSnapshotValue('2', snapshot))
    self.assertEquals(
        [1, 2, 3], JsonSnapshotHelper.ToJsonSnapshotValue([1, 2, 3], snapshot))
    d = {'a': 'A', 'b': 2, 'c': [1, 2, 3]}
    self.assertEquals(
        d, JsonSnapshotHelper.ToJsonSnapshotValue(d, snapshot))
    self.assertEquals({'_type': 'JsonSnapshot'}, snapshot.to_json_object())

    # Wrapped values dont affect snapshot
    self.assertEquals(
        d,
        JsonSnapshotHelper.ToJsonSnapshotValue(TestWrappedValue(d), snapshot))
    self.assertEquals({'_type': 'JsonSnapshot'}, snapshot.to_json_object())

    # types dont affect snapshot
    self.assertEquals(
        'type dict',
        JsonSnapshotHelper.ToJsonSnapshotValue(dict, snapshot))
    self.assertEquals({'_type': 'JsonSnapshot'}, snapshot.to_json_object())

    # methods dont affect snapshot
    self.assertEquals(
        'Method "test_to_json_snapshot_value"',
        JsonSnapshotHelper.ToJsonSnapshotValue(
            self.test_to_json_snapshot_value, snapshot))
    self.assertEquals({'_type': 'JsonSnapshot'}, snapshot.to_json_object())

    # exceptions dont affect snapshot
    self.assertEquals(
      'KeyError: \'Hello, World\'',
        JsonSnapshotHelper.ToJsonSnapshotValue(KeyError('Hello, World'),
                                               snapshot))
    self.assertEquals({'_type': 'JsonSnapshot'}, snapshot.to_json_object())

    # JsonSnapshotableEntity definition written into snapshot
    ll = TestLinkedList('X')
    ref = JsonSnapshotHelper.ToJsonSnapshotValue(ll, snapshot)
    self.assertEquals({'_type': 'EntityReference', '_id': 1}, ref)
    expect = {'_type': 'JsonSnapshot',
              '_subject_id': 1,
              '_entities': {1: {'_id': 1,
                                'class': 'type TestLinkedList',
                                'name': 'X'}}
              }
    self.assertEquals(expect, snapshot.to_json_object())
    self.assertEquals(1, snapshot.find_entity_for_object(ll).id)

  def test_snapshot_make_entity(self):
    """Test snapshotting JsonSnapshotableEntity objects into entities."""
    elem = TestLinkedList('Hello')
    snapshot = JsonSnapshot()
    entity = snapshot.make_entity_for_object(elem)
    found = snapshot.find_entity_for_object(elem)
    self.assertEquals(found, entity)
    self.assertEquals(id(found), id(entity))
    self.assertItemsEqual({'_subject_id': 1,
                           '_type': 'JsonSnapshot',
                           '_entities': [{'_id': 1, 'name': 'Hello'}]},
                          snapshot.to_json_object())

  def test_snapshot_make_transitive_entity(self):
    """Test snapshotting compound entities."""
    elem = TestLinkedList('First', next_elem=TestLinkedList('Second'))
    snapshot = JsonSnapshot()
    snapshot.make_entity_for_object(elem)
    entity = snapshot.make_entity_for_object(elem.next)
    found = snapshot.find_entity_for_object(elem.next)
    self.assertEquals(found, entity)
    self.assertEquals(id(found), id(entity))
    self.assertItemsEqual({'_subject_id': 1,
                           '_type': 'JsonSnapshot',
                           '_entities': [{'_id': 1, 'name': 'First',
                                          '_edges':[{'_to': 2}]},
                                         {'_id': 2, 'name': 'Second'}]},
                          snapshot.to_json_object())

  def test_snapshot_full_entities(self):
    """Test snapshotting an entity whose data are all entities."""
    snapshot = JsonSnapshot(title='Test Graph')
    entity_a = snapshot.new_entity(name='Entity Name')
    expect_a = {'_id': 1, 'name': 'Entity Name'}

    entity_b = snapshot.new_entity(data=1234, type='scalar')
    expect_b = {'_id': 2, 'data': 1234, 'type': 'scalar'}

    entity_c = snapshot.new_entity(data=3.14, type='real')
    expect_c = {'_id': 3, 'data': 3.14, 'type': 'real'}

    snapshot.edge_builder.make(entity_a, 'A to B', entity_b)
    expect_ab = {'_to': entity_b.id, 'label': 'A to B'}

    snapshot.edge_builder.make(entity_a, 'A to C', entity_c)
    expect_ac = {'_to': entity_c.id, 'label': 'A to C'}

    expect_a['_edges'] = [expect_ab, expect_ac]
    expect = {'_subject_id': 1,
              '_type': 'JsonSnapshot',
              '_entities': [expect_a, expect_b, expect_c],
              'title': 'Test Graph'}
    json_obj = snapshot.to_json_object()
    self.assertItemsEqual(expect, json_obj)

  def test_snapshot_fields(self):
    """Test snapshotting an entity whose data are simple values."""
    snapshot = JsonSnapshot(title='Test Snapshot')
    entity_a = snapshot.new_entity(name='Entity Name')
    expect_a = {'_id': 1, 'name': 'Entity Name'}

    expect_edges = []
    snapshot.edge_builder.make(entity_a, 'scalar', 1234)
    expect_edges.append({'_value': 1234, 'label': 'scalar'})

    snapshot.edge_builder.make(entity_a, 'real', 3.14)
    expect_edges.append({'_value': 3.14, 'label': 'real'})

    expect = {'_subject_id': 1,
              '_type': 'JsonSnapshot',
              '_entities': [expect_a],
              'title': 'Test Snapshot'}
    json_obj = snapshot.to_json_object()

    self.assertItemsEqual(expect, json_obj)

  def test_snapshot_edge_builder(self):
    """Test focused on snapshot.edge_builder property."""
    snapshot = JsonSnapshot(title='Test Snapshot')
    entity_a = snapshot.new_entity(name='Entity A')
    entity_b = snapshot.new_entity(name='Entity B')
    expect_a = {'_id': 1, 'name': 'Entity A'}

    expect_edges = []
    snapshot.edge_builder.make_mechanism(entity_a, 'B', entity_b)
    expect_edges.append({'_to': 2, 'label': 'B', 'relation': 'MECHANISM'})

    snapshot.edge_builder.make_control(entity_a, 'field', -321)
    expect_edges.append({'_value': -321, 'label': 'field',
                         'relation': 'CONTROL'})

    expect = {'_subject_id': 1,
              '_type': 'JsonSnapshot',
              '_entities': [expect_a],
              'title': 'Test Snapshot'}
    json_obj = snapshot.to_json_object()

    self.assertItemsEqual(expect, json_obj)

  def test_snapshot_list(self):
    a = TestLinkedList('A')
    b = TestLinkedList('B')
    c = TestLinkedList('C')
    a.next = b
    b.next = c

    snapshot = JsonSnapshot()
    self.assertIsNone(snapshot.find_entity_for_object(b))
    self.assertIsNone(snapshot.find_entity_for_object(b)) # Still none
    snapshot.add_object(a)
    json_object = snapshot.to_json_object()

    have_b = snapshot.find_entity_for_object(b)
    self.assertEquals(2, have_b.id)
    entity_b = snapshot.make_entity_for_object(b)
    self.assertEquals(id(have_b), id(entity_b))

    have_c = snapshot.find_entity_for_object(c)
    entity_c = snapshot.make_entity_for_object(c)
    self.assertEquals(id(have_c), id(entity_c))
    self.assertEquals(3, entity_c.id)

    expect = {
        '_subject_id': 1,
        '_type': 'JsonSnapshot',
        '_entities': [
            {'_id': 1, 'name': 'A', '_edges': [{'_to': 2}]},
            {'_id': 2, 'name': 'B', '_edges': [{'_to': 3}]},
            {'_id': 3, 'name': 'C'}]}

    self.assertItemsEqual(expect, json_object)


if __name__ == '__main__':
  unittest.main()
