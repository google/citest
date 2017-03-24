# Copyright 2016 Google Inc. All Rights Reserved.
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

"""Helper classes and methods for special case interpreting Snapshot Entities.

These classes rewrite some of the entities to simplify their reporting
interpretations to provide a more concise data model.
"""

class EdgeLabelValueTransformer(object):
  """Transforms a snapshot entity edge label and value depending on context.


  The instance is bound to the original entity and is called with each edge
  to extract the label and value for that edge giving the instance a chance
  to rewrite the label and/or value, or to ignore it completely.
  """

  @property
  def entity(self):
    """The SnapshotEntity dictionary bound at construction."""
    return self.__entity

  @property
  def entity_manager(self):
    """The EntityManager bound at construction."""
    return self.__entity_manager

  @staticmethod
  def _find_edge(entity, label_name):
    """Return the edge with the given label name.

    Args:
      entity: [dict] The snapshot entity dict
      label_name: [string] The label name we're looking for.
    """
    if entity is None:
      return None
    for edge in entity.get('_edges', []):
      if edge.get('label') == label_name:
        return edge
    return None

  def __init__(self, entity, entity_manager):
    """Constructor."""
    self.__entity = entity
    self.__entity_manager = entity_manager

  def __call__(self, edge):
    """Returns label, value for the given edge.

    Args:
      edge: [dict] The edge dictionary

    Returns:
      label, value tuple where label is None means ignore the edge.
    """
    label = edge.get('label', '?unlabeled')
    value = edge.get('_value', None)
    return label, value


class PathPredicateResultLabelValueTransformer(EdgeLabelValueTransformer):
  """Transformer for PathPredicateResult snapshot entities.

  PathPredicateResults return a list of values at a given path.
  If the path does not contain lists, there will be only one value
  then remove the list wrapper from the value since it is not needed.
  """

  def __init__(self, entity, entity_manager):
    """Constructor."""
    super(PathPredicateResultLabelValueTransformer, self).__init__(
        entity, entity_manager)

  def __call__(self, edge):
    """Implements EdgeLabelValueTransformer."""
    label, value = super(
        PathPredicateResultLabelValueTransformer, self).__call__(edge)
    if not isinstance(value, list) or len(value) != 1:
      return label, value
    if label != 'Path Values' and label != 'Value Justifications':
      return label, value
    return label, value[0]


class NumericIndexedLabelValueTransformer(EdgeLabelValueTransformer):
  """Base class for handling results that use '[n]' indexed edge labels.

  This base class determines if there is only one element in the array.
  If so, it can unpack that one element value to replace the array container.
  """

  @property
  def has_exactly_one(self):
    """True if there is only a [0] label for the array."""
    return self.__exactly_one

  def __init__(self, key_name, one_label_name, entity, entity_manager):
    """Constructor.

    Args:
      key_name: [string] The label name for the edge to the value array.
      one_label_name: [string] The label name to use for the edge to the value
         if there is only one value and we replace the array with it.
    """
    super(NumericIndexedLabelValueTransformer, self).__init__(
        entity, entity_manager)

    results = self._find_edge(self.entity, key_name)
    one = None
    zero = None
    if results is not None:
      entity_id = results.get('_to')
      results_entity = self.entity_manager.lookup_entity_with_id(entity_id)
      zero = self._find_edge(results_entity, '[0]')
      one = self._find_edge(results_entity, '[1]')

    self.__key_name = key_name
    self.__one_label_name = one_label_name
    self.__exactly_one = zero is not None and one is None

  def __call__(self, edge):
    """Implements EdgeLabelValueTransformer.

    If there is only one value and this is the edge to the array containing it,
    then treat the edge (to the array) as if it were the inner edge
    (to the value).
    """
    label, value = super(
        NumericIndexedLabelValueTransformer, self).__call__(edge)
    if not self.__exactly_one or label != self.__key_name:
      return label, value

    entity_id = edge.get('_to')
    results_entity = self.entity_manager.lookup_entity_with_id(entity_id)
    zero = self._find_edge(results_entity, '[0]')
    value_id = zero.get('_to')
    value = {'_type': 'EntityReference', '_id': value_id}

    return (self.__one_label_name, value) if value else (None, value)


class SequencedResultLabelValueTransformer(
    NumericIndexedLabelValueTransformer):
  """Handle edges to "SequencedResult" objects.

  If the result contains exactly one value, replace the array of values with
  just the single value to get rid of the array indirection.
  """
  def __init__(self, entity, entity_manager):
    """Constructor."""
    super(SequencedResultLabelValueTransformer, self).__init__(
        'Results', 'Result', entity, entity_manager)

  def __call__(self, edge):
    """Implements EdgeLabelValueTransformer."""
    if self.has_exactly_one:
      # Drop the count attribute.
      label = edge.get('label')
      if label == '#':
        return None, None

    return super(
        SequencedResultLabelValueTransformer, self).__call__(edge)


class ContractVerifyResultLabelValueTransformer(EdgeLabelValueTransformer):
  """Handle edges to "ContractVerifyResult" objects.

  If the result contains exactly one clause, replace the array of clauses with
  just the single clause to get rid of the array indirection.
  """
  def __init__(self, entity, entity_manager):
    """Constructor."""
    super(ContractVerifyResultLabelValueTransformer, self).__init__(
        entity, entity_manager)
    results = self._find_edge(entity, 'Clause Results')
    value = results.get('_value') if results is not None else None
    self.__has_exactly_one = isinstance(value, list) and len(value) == 1

  def __call__(self, edge):
    """Implements EdgeLabelValueTransformer."""
    label, value = (
        super(ContractVerifyResultLabelValueTransformer, self).__call__(edge))

    if label != 'Clause Results':
      return label, value

    if self.__has_exactly_one:
      return 'Clause Result', value[0]

    return label, value


class ObservationVerifyResultLabelValueTransformer(EdgeLabelValueTransformer):
  """Transformer for ObservationVerifyResult snapshot entities.

  ObservationVerifyResult return a list of PredicateResult for each of the
  observed values, breaking them up into a list of good results and bad.
  However, if we only observed one object then we dont need a list of results,
  and there is no need to break up into good and bad, just have the
  single result.
  """

  def __determine_observed_single(self, entity, entity_manager):
    """Determine whether the entity observed a single object."""
    observations = self._find_edge(self.entity, 'Observation')
    objects = None
    if observations is not None:
      # The observation edge contains an entity reference to the objects.
      # So, we need to fetch the entity, then lookup the Objects within it,
      # and get the value to determine how big the list of observations was.
      entity_id = observations.get('_to')
      if entity_id is not None:
        observation_entity = entity_manager.lookup_entity_with_id(
            entity_id)
        objects_entity = self._find_edge(observation_entity, 'Objects')
        objects = (None if objects_entity is None
                   else objects_entity.get('_value'))
    return isinstance(objects, list) and len(objects) == 1

  def __determine_good_and_bad(self, entity):
    # Track whether we have both good and bad results.
    # We'll simplify or prune labels if only one or the other
    num_good = len((self._find_edge(self.entity, 'Good Results') or {}).get('_value', []))
    num_bad = len((self._find_edge(self.entity, 'Bad Results') or {}).get('_value', []))
    total_results = num_good + num_bad
    good_and_bad = num_good != 0 and num_bad != 0
    return total_results, good_and_bad

  def __init__(self, entity, entity_manager):
    """Constructor."""
    super(ObservationVerifyResultLabelValueTransformer, self).__init__(
        entity, entity_manager)

    self.__observed_single = self.__determine_observed_single(
        entity, entity_manager)
    self.__total_results, self.__good_and_bad = self.__determine_good_and_bad(
        entity)

  def __call__(self, edge):
    """Implements EdgeLabelValueTransformer."""
    label, value = super(
        ObservationVerifyResultLabelValueTransformer, self).__call__(edge)

    if (label == 'Good Results' or label == 'Bad Results'):
      if isinstance(value, list) and len(value) == 1:
        value = value[0]
      if not self.__good_and_bad:
        return ('Result', value)

    return label, value


LABEL_VALUE_TRANSFORMER_TYPE = {
    'type PathPredicateResult': PathPredicateResultLabelValueTransformer,
    'type ObservationVerifyResult':
        ObservationVerifyResultLabelValueTransformer,
    'type SequencedPredicateResult': SequencedResultLabelValueTransformer,
    'type ContractVerifyResult': ContractVerifyResultLabelValueTransformer,
}


def get_edge_label_value_transformer(entity, entity_manager):
  """Returns factory for transforming edges to label, value pairs.

  Returns a callable that takes an snapshot edge specification and returns
  the label and value it denotes. A label of None indicates to ignore the edge.
  """
  name = entity.get('class', None)
  return LABEL_VALUE_TRANSFORMER_TYPE.get(
      name, EdgeLabelValueTransformer)(entity, entity_manager)
