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


"""Implements a graph representing data model state at a point in time.

The graph is called a "JsonSnapshot" (snapshot) to reflect fact that it is a
point in time and represented using JSON. A snapshot consists of data objects
(entities) that have relationships (edges) to one another. Entities and edges
can be annotated using arbitrary sets of name/value metatdata.

The Snpashot, Entities, and Edges are all specific to snapshots and expressing
the data model as opposed to implementing the data model. An interface,
"JsonSnapshotable" is used to import actual data model implementations into
a snapshot. Adding this interface to a class and implementing its
"export_to_json_snapshot()" method allows a runtime data model implementation
to be captured as a SnapshotEntity within a JsonSnapshot defined here.

It is important that this is a snapshot because we want to capture how values
change over time. Simply modeling the relationship among data without the
current values would miss the distinction of what the actual values were at
different points in time.

Snapshots support a meta-model where relationships can be specified using
the following names and concepts:
  INPUT: The value is used as input. Input is used to create a work product,
     and the value may change from time to time.
  OUTPUT: The value is the result of a work product.
  DATA: The value is a data value, usually input or output, but may differ
     depending on your perspective but is usually clear from the context.
     This is intended for generic entities that are building blocks for
     different contexts, sometimes input and sometimes output.
  ERROR: The value denotes an error. Errors are different from INVALID,
     in that an error typically indicates a failure to perform or complete
     the operation, where as an INVALID result indicates that the operation
     completed but did not perform as expected.
  MECHANISM: The value describes a mechanism used to perform or assist in
     the creation or evaluation of a work product.
  CONTROL: The value is used as a configuration parameter. This is different
     from an INPUT though may not always be clear exactly which to use.
     Controls are usually consumed by mechanisms whereas inputs are consumed
     by operations.
  VALID: The value denotes an expected or desirable result. This usually
     subsumes an output but draws attention to the significance of it being
     of interest from a testing perspective.
  INVALID: The value denotes an unexpected or undesirable result. This usually
     subsumes an output but draws attention to the significance of it being
     of interest from a testing perspective.
"""

import datetime
import json
import types


def _normalize_metadata_value(value):
  """Convert value into an appropriate format to use as metadata.

  Args:
    value: [obj] A value of a primitive type.

  Returns:
    The encoding of value to use as a metadata value.
  """
  if isinstance(value, (basestring, bool, int, long, float, None.__class__)):
    return value
  if isinstance(value, type):
    return 'type ' + value.__name__
  if isinstance(value, BaseException):
    return 'exception ' + value.__class__.__name__
  raise TypeError('{0} is not a valid metadata type: {1}'.format(
      value.__class__, value))


def _normalize_metadata_kwargs(metadata):
  """Convert metadata dictionary into an appropriate format for use as metadata.

  Args:
    metadata: [dict] The dictionary of metadata values.

  Returns:
    A dictionary of appropriately encoded values.
  """
  result = {}
  for key, value in metadata.items():
    result[key] = _normalize_metadata_value(value)
  return result


class JsonSnapshotable(object):
  """Interface for storing an object into a JsonSnapshot."""

  def to_snapshot_value(self, snapshot):
    """Convert this instance into the value to write into the snapshot.

    Args:
      snapshot: [Snapshot] The snapshot that the value will be stored in.
          This is intended for reference, not necessarily to write the value
          into the snapshot. For some specialized classes (entity), the value
          to write into the snapshot may wish to reference existing entities
          or require side effects into the snapshot in order to produce the
          value.

    Returns:
      Object that JsonSnapshot knows how to render.
    """
    raise NotImplementedError('{0}.to_snapshot_value'.format(self.__class__))


class JsonSnapshotableEntity(JsonSnapshotable):
  """Interface for storing a composite object into a JsonSnapshot."""

  def to_snapshot_value(self, snapshot):
    """Convert this instance into the value to write into the snapshot.

    This will create an entity in the snapshot and encode this
    instance into the entity using the export_to_json_snapshot method. If
    the entity already exists then it will return the existing entity.
    """
    return snapshot.make_entity_for_object(self)

  def export_to_json_snapshot(self, snapshot, entity):
    """Store this object state into the snapshot.

    The stored state can reference other objects already in the snapshot,
    or add multiple objects, and reference (or not) among them.

    Args:
      snapshot: [JsonSnapshot] The snapshot owning the entity is used to
          relate to other entities.
      entity: [SnapshotEntity] The snapshot entity to export into.
    """
    raise NotImplementedError('{0}.export_to_json_snapshot'.format(
        self.__class__))


class Edge(object):
  """Represents a relationship between entities (an edge in the a graph).

  Edges are annotated relationships to values. A value is either a
  SnapshotEntity (which links to another first class node in the graph)
  or a primitive value, which is annotated using a reserved "_value" annotation
  on the edge itself.

  Edges are intended to be directional and unique. However, two entities can
  share multiple edges between them where each edge represents a distincly
  different relationship. The source endpoint is implicit and later associated
  with the entity that "has" the relationship. The target endpoint is bound
  to the edge (or the _value annotation). Reserved annotations have leading
  underscores in their names.

  Standard annotations on an edge include:
     _to: [int] If present then this edge references another entity.
        The referenced entity has the |_id| matching the edge's |_to|.
     _value: [any] If present then this edge references a  value
        that is an implied entity specifying this value.
     label: The name of the relationship for display purposes.
     relation: The type of relationship
  """

  @property
  def metadata(self):
    """Metadata annotations on the edge.

    The metadata dictionary on the node should not be modified directly.
    Instead use add_metadata() to add additional annotations.
    """
    return self.__metadata

  @property
  def target(self):
    """Returns the target node, if any."""
    return self.__target

  @property
  def value(self):
    """Returns the value."""
    return self.__value

  def __init__(self, _to_json_object, _target=None, _value=None, **metadata):
    """Constructs the edge.

    Args:
      _to_json_object: [obj (Edge)] Converts edge to json object to serialize.
      _target: [SnapshotEntity] The target entity, or None.
      _value: [SnapshotEntity] The edge value, or None if same as _target.
      metadata: [kwargs] Additional metadata annotations for the edge.
         The keys are determined by the Entity at the source of the edge.
    """
    self.__metadata = _normalize_metadata_kwargs(metadata)
    self.__to_json_object = _to_json_object
    if _target is not None and not isinstance(_target, SnapshotEntity):
      raise TypeError('{0} is not SnapshotEntity'.format(_target.__class__))
    self.__target = _target
    self.__value = _value if _value is not None else _target

  def __str__(self):
    return '  edge to {0} /{1}'.format(self.__target, self.metadata)

  def add_metadata(self, key, value):
    """Adds a new metadata key.

    Args:
      key: [string] Keys beginning with '_' are reserved for internal use.
      value: [any] The metadata value.
    """
    value = _normalize_metadata_value(value)
    self.__metadata[key] = value

  def to_json_object(self):
    """Serializes this edge into a object that is json encodable."""
    return self.__to_json_object(self)


class SnapshotEntity(object):
  """Represents an entity in a snapshot.

  An entity is a container with an id and metadata that references an
  object snapshot value.

  Entities are intended to be created by JsonSnapshots. Their id is an
  opaque key   allocated by the snapshot creating the entity.

  Metadata is a key/value dictionary where the keys are defined by the
  Snapshot containing the entities.

  Standard annotations include:
     _type:  [string] The type of element within the snapshoting/journaling
        system. Consider this the container,

     _timestamp: [float] The time that the data was recorded.
     _id: [int] The entities identifier used for references.
     _edges: [list of dict] The list of edges from the entity.
        This can be thought of as the entities properties.
        All the other attributes are metadata.
     _default_relation [string]: A default relationship that one should
        assume inbound edges have if they do not explicitly specify one.
        This is currently mostly used for entities that are members of
        lists where the list has no way to specify individual elements.
     class: The class of the original instance that this entity represents.
  """

  @property
  def id(self):
    """Returns the entity's id."""
    # pylint: disable=invalid-name
    return self.__id

  @property
  def metadata(self):
    """Returns the entity metadata.

    This is not intended to be modified directly, instead use add_metadata()
    """
    return self.__metadata

  @property
  def edges(self):
    """Returns all the edges originating from this entity."""
    return self.__ordered_edges

  @property
  def edge_lists(self):
    """Returns a list of edge lists from this entity to other entities.

    Each list contains all the edges to a different target entity.
    """
    return self.__entity_edges.values()

  def __init__(self, entity_id, **metadata):
    """Constructs an entity.

    Args:
      entity_id: [id]  Determined by the Snapshot containing it.
      metadata: [kwargs] Additional metadata can be provided. They keys are
         determined by the Snapshot but not checked here.
    """
    self.__id = entity_id
    self.__metadata = _normalize_metadata_kwargs(metadata)
    self.__ordered_edges = []
    self.__entity_edges = {}  # subset that reference entities
    self.__value_edges = []   # subset that reference values

  def add_metadata(self, key, value):
    """Adds a new metadata key.

    Args:
      key: [string] Keys beginning with '_' are reserved for internal use.
      value: [any] The metadata value.
    """
    value = _normalize_metadata_value(value)
    self.__metadata[key] = value

  def add_edge(self, edge):
    """Adds an edge that has already been constructed.

    This method is typically called from JsonSnapshotEdgeBuilder, which
    creates the edge being added here. This is because the edge typically
    needs the snapshot to reference other entities, and the entity does not
    typically have access to that.

    We could add another helper method here, make_edge that essentially
    fronts snapshot.edge_builder.make() but it isnt clear there is a point
    to doing that other than increasing the surface area of API.

    Args:
      edge: [Edge] The existing edge instance to add.
    """
    if not isinstance(edge, Edge):
      raise TypeError('{0} is not an Edge'.format(edge.__class__))

    target = edge.target
    if target is not None:
      to_id = edge.target.id
      if not to_id in self.__entity_edges:
        self.__entity_edges[to_id] = [edge]
      else:
        self.__entity_edges[to_id].append(edge)
    else:
      self.__value_edges.append(edge)
    self.__ordered_edges.append(edge)
    return edge

  def to_json_object(self):
    """Serializes this entity into a object that is json encodable."""
    result = {'_id': self.__id}

    edges = []
    for edge in self.edges:
      edges.append(edge.to_json_object())
    if edges:
      result['_edges'] = edges

    result.update(self.__metadata)
    return result


class JsonSnapshotHelper(object):
  """Helper class for implementing JsonSnapshotable."""

  # pylint: disable=too-few-public-methods
  @classmethod
  def ToJsonSnapshotValue(cls, value, snapshot):
    """Convert value into snapshot equivalent.

    For the most part, this is the identity if value is a primitive type.
    However lists and dictionaries may reference other entities that need
    to be snapshotted. For example references to other entities, or other
    object types that need to be converted.
    """
    # pylint: disable=invalid-name
    # pylint: disable=unused-argument
    # pylint: disable=too-many-return-statements

    if isinstance(value, JsonSnapshotable):
      # Turn value into the snapshot value (which might be an entity
      # or wrapped value) and continue the method depending on the new
      # value type returned.
      value = value.to_snapshot_value(snapshot)

    if isinstance(value, (basestring, bool, int, long, float, None.__class__)):
      return value

    if isinstance(value, SnapshotEntity):
      # The entity already exists in the snapshot. Presumably this
      # entity was the result of to_snapshot_value above (or in an earlier
      # call), which wrote the entity into the snapshot so here we merely
      # need to reference the existing entity within the snapshot.
      return {'_type': 'EntityReference', '_id': value.id}

    if isinstance(value, list):
      return [cls.ToJsonSnapshotValue(elem, snapshot) for elem in value]

    if isinstance(value, dict):
      result = {}
      for name, elem in value.items():
        result[name] = cls.ToJsonSnapshotValue(elem, snapshot)
      return result

    if isinstance(value, type):
      return 'type ' + value.__name__

    if isinstance(value, BaseException):
      return '{0}: {1}'.format(value.__class__.__name__, value)

    if isinstance(value, types.MethodType):
      return 'Method "{0}"'.format(value.__name__)

    if isinstance(value, types.LambdaType):
      return 'Lambda "{0}"'.format(value.func_name)

    if isinstance(value, datetime.datetime):
      return value.isoformat()

    raise TypeError(
        '{0} is not implicitly JsonSnapshotable: {1!r}'.format(
            value.__class__, value))

  @staticmethod
  def AssertExpectedValue(expect, have, msg=None):
    """Verify that two values produce the same representation in a snapshot.

    This is to support testing so that we can test equivalence of objects
    within our data model and report the details on error.

    Args:
      expect: [any] The python value we expect.
      have:   [any] The python value we have.
      msg:    [string]  If provided, the message to raise on failure.

    Raises:
      AssertionError
    """
    # pylint: disable=invalid-name
    if expect == have:
      return

    # The objects might still be equivalent.
    # Snapshot each and compare the snapshots.
    snapshot = JsonSnapshot()
    expect_jsv = JsonSnapshotHelper.ToJsonSnapshotValue(expect, snapshot)
    expect_so = snapshot.to_json_object()

    snapshot = JsonSnapshot()
    have_jsv = JsonSnapshotHelper.ToJsonSnapshotValue(have, snapshot)
    have_so = snapshot.to_json_object()

    if have_jsv == expect_jsv and have_so == expect_so:
      return

    if not msg:
      expect_this = expect_so if isinstance(expect_jsv, dict) else expect_jsv
      have_this = have_so if isinstance(have_jsv, dict) else have_jsv

      # Display the json representations for detailed reporting.
      encoder = json.JSONEncoder(indent=2, separators=(',', ': '))
      expect_text = encoder.encode(expect_this)
      have_text = encoder.encode(have_this)
      msg = '\n--- EXPECT ---\n{0}\n--- GOT ---\n{1}\n---------'.format(
          expect_text, have_text)
    raise AssertionError(msg)

  @staticmethod
  def ValueToEncodedJson(value):
    """Convert an object into its JSON-encoded JsonSnapshot equivalent.

    This is to support testing.

    Args:
      value: [obj] The value we want to encode.
    """
    # pylint: disable=invalid-name

    snapshot = JsonSnapshot()
    value_obj = JsonSnapshotHelper.ToJsonSnapshotValue(value, snapshot)
    snapshot_obj = snapshot.to_json_object()
    json_obj = snapshot_obj if isinstance(value_obj, dict) else value_obj
    return json.JSONEncoder(indent=2, separators=(',', ': ')).encode(json_obj)


class JsonSnapshotEdgeBuilder(object):
  """A helper class for relating data within a snapshot.

  The methods in this class typically take a **metdata kwarg parameter
  whose values will be annotations for the created edge. The positional
  parameters have names starting with '_' to minimize the risk of having
  name clashes between these internal parameters and arbitrary metadata
  annotation keys.

  This edge builder defines an meta-data model that is acting as a standard,
  at least for the time being.
  """

  #pylint: disable=missing-docstring

  def __init__(self, snapshot):
    """Constructs builder.

    Args:
      snapshot: [JsonSnapshot] The snapshot holding the entities.
    """
    self.__snapshot = snapshot
    self.__value_helper = JsonSnapshotHelper

  def new_edge(self, _label, _value, **metadata):
    """Creates a new edge to a target value.

    This method creates a directional edge to the supplied value.
    The edge will later be associated with an entity, giving it an
    implicit initial endpoint.

    Args:
      _label: [string] The value of the 'label' metadata attribute.
      _value: [obj] The value the edge is related to.
         This can be either a SnapshotEntity, JsonSnapshotable value
         contained by an entity, or primitive json value.
      **metadata: [kwargs] Remaining metadata values.

    Returns:
      A snapshot edge.
    """
    if isinstance(_value, JsonSnapshotable):
      _value = _value.to_snapshot_value(self.__snapshot)

    if isinstance(_value, SnapshotEntity):
      return self.__new_entity_edge(_value, label=_label, **metadata)

    value = self.__value_helper.ToJsonSnapshotValue(_value, self.__snapshot)
    return self.__new_value_edge(value, label=_label, **metadata)

  @staticmethod
  def  __new_entity_edge(_entity, **metadata):
    def to_json_object(edge):
      """Serializes the edge into a object that is json encodable."""
      result = {}
      result['_to'] = edge.target.id
      result.update(edge.metadata)
      return result
    return Edge(_target=_entity, _to_json_object=to_json_object, **metadata)

  @staticmethod
  def  __new_value_edge(_value, **metadata):
    def to_json_object(edge):
      """Serializes the edge into a object that is json encodable."""
      result = {}
      if _value is not None:
        result['_value'] = _value
      if edge.metadata:
        result.update(edge.metadata)
      return result
    return Edge(_value=_value, _to_json_object=to_json_object, **metadata)

  def make(self, _from, _label, _value, **metadata):
    """Creates a new directional edge from |_from| to |_value|.

    The edge will be labeled with |_label| and annotated with |**metadata|
    and added to |_from|.

    Args:
      _from: [SnapshotEntity] The entity to attach the edge source endpoint to.
      _label: [string] The value of a 'label' annotation.
      _value: [any] See new_edge().
      metadata: [kwargs] Additional annotation for the edge.
    """
    return _from.add_edge(self.new_edge(_label, _value, **metadata))

  def make_input(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='INPUT', **metadata))

  def make_output(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='OUTPUT', **metadata))

  def make_mechanism(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='MECHANISM', **metadata))

  def make_control(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='CONTROL', **metadata))

  def make_data(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='DATA', **metadata))

  def make_error(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='ERROR', **metadata))

  def make_valid(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='VALID', **metadata))

  def make_invalid(self, _from, _label, _value, **metadata):
    return _from.add_edge(
        self.new_edge(_label, _value, relation='INVALID', **metadata))

  @staticmethod
  def object_count_to_summary(obj, subject='object', plural=None):
    """A helper method for returning a string indicating a cardinality.

    Args:
      obj: [dict, or list] The object whose cardinality we are interested in.
      subject: [string] The singular name of the entities we are counting.
      plural: [string] The plural name of entities we are counting.
         None indicates just add an 's'.
    Returns:
      A string summarizing how many things we have.
    """
    count = 0 if not obj else len(obj)
    if count == 1:
      return '1 ' + subject

    if plural is None:
      plural = subject + 's'
    return '{count} {plural}'.format(count=count, plural=plural)

  @staticmethod
  def determine_valid_relation(is_valid):
    """Return specific relation name depending on validity of the value."""
    return 'VALID' if is_valid else 'INVALID'


class JsonSnapshot(object):
  """Represents a snapshot of a data model relating entities to one another.

  A snapshot is a list of entities, each of which can have arbitrary
  relationships to values. Values are either primitive types or other
  entities.

  Relationships are edges that connect entities to values. These edges can
  be further annotated with other attributes describing the relationship.
  The interpretation of these annotations is generally not defined by this
  module, but can be defined by the entities themselves.

  Primitive values are stored as metadata on the edge itself for brevity.
  By convention, internal (standard) annotations have a leading '_', and
  those left to the "user domain" do not.

  Entities (and snapshots) are also annotated. All these objects are
  stored (in json) using dictionaries. There is no explicit distinction
  in the JSON between metadata and the objects representation.

  Standard annotations include:
     _subject_id: [int] The "main" entity being snapshotted.
         This is currently a hack, assuming that a snapshot is of a
         particular object. Really the subject are all the roots but
         this requires work to figure out so isnt easily inspectable.
     _title: [string] The title for the snapshot, if any.
     _entities: [dict of Entity] This is a map of entities keyed by
         their _id. Note that JSON forces these keys to be strings
         but we're currently storing the attributes as integers.
         So to perform a lookup in this dictionary, you will need to
         convert the integer keys into strings.
  """

  @property
  def metadata(self):
    """Metadata annotations on the snapshot.

    The metadata should not be modified directly.  Instead use add_metadata().
    """
    return self.__metadata

  @property
  def edge_builder(self):
    """Facilitate associating relations among data within the snapshot."""
    return self.__edge_builder

  def __init__(self, **metadata):
    """Constructs snapshot.

    Args:
      metadata: [kwargs] Metadata to associate with the snapshot.
    """
    self.__last_id = 0
    self.__entities = {}
    self.__snapshotable_entities = {}
    self.__metadata = _normalize_metadata_kwargs(metadata)
    self.__subject_entity = None
    self.__edge_builder = JsonSnapshotEdgeBuilder(self)

  def add_metadata(self, key, value):
    """Adds a new metadata key.

    Args:
      key: [string] Keys beginning with '_' are reserved for internal use.
      value: [any] The metadata value.
    """
    value = _normalize_metadata_value(value)
    self.__metadata[key] = value

  def add_object(self, snapshotable_entity):
    """Adds snapshotable data into the snapshot.

    Args:
      snapshotable_entity: [JsonSnapshotableEntity] Entity to add to snapshot.
    """
    self.make_entity_for_object(snapshotable_entity)

  def make_entity_for_object(self, snapshotable):
    """Returns a possibly shared node for |snapshotable|.

    Args:
      snapshotable: [JsonSnapshotable] Data for a unique entity. The
        entity may already exist with |snapshotable| (as opposed to an
        existing node for different snapshotable).
    """
    if not isinstance(snapshotable, JsonSnapshotable):
      raise TypeError(
          '{0} is not JsonSnapshotable'.format(snapshotable.__class__))

    entity = self.find_entity_for_object(snapshotable)
    if entity is None:
      entity = self.new_entity()
      entity.add_metadata('class', snapshotable.__class__)
      self.__snapshotable_entities[id(snapshotable)] = entity
      snapshotable.export_to_json_snapshot(self, entity)
    return entity

  def new_entity(self, **metadata):
    """Returns a new entity.

    Args:
      metadata: [kwargs] Metadata to bind to the node.
      """
    self.__last_id += 1
    entity = SnapshotEntity(entity_id=self.__last_id, **metadata)
    self.__entities[self.__last_id] = entity
    if self.__subject_entity is None:
      self.__subject_entity = entity
    return entity

  def find_entity_for_object(self, snapshotable):
    """Find a entity containing data, if any.

    Args:
      snapshotable: [JsonSnapshotable] The data bound to the entity.

    Returns:
      None if no entity contains |snapshotable|.
    """
    return self.__snapshotable_entities.get(id(snapshotable))

  def get_entity(self, entity_id):
    """Looks up the entity with the given entity_id.

    Args:
      entity_id: [any]  The id comes from previously allocated entity.

    Raises:
      KeyError if the entity_id was not known.
    """
    return self.__entities[entity_id]

  def to_json_object(self):
    """Serializes this snapshot into a object that is json encodable."""
    result = {'_type': 'JsonSnapshot'}
    if self.__entities:
      result['_subject_id'] = self.__subject_entity.id
      entities = {}
      for key, entity in self.__entities.items():
        entities[key] = entity.to_json_object()
      result['_entities'] = entities

    if self.__metadata:
      result.update(self.__metadata)
    return result
