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

"""Provides APIs for specifying predicates on JSON objects.

The API is for specifying attributes to extract from within the JSON object,
and analyzing the corresponding values using standard types of operations
against their values. The operations are typically comparator types of
operations to see if their values are consistent with expectations.
"""
# pylint: disable=relative-import


from .json_error import JsonError

# This module is intended to support the higher level json_predicate.* modules.
# To that end, the lookups populate PredicateResult objects rather than just
# returning values, so are heavier weight that would be otherwise.
from .path_value import (
    PATH_SEP,
    build_path,
    PathValue)


# json_predicate.predicate provides a mechanism using callable objects
# to validate a a value. It is used to support the finder
# module to specify how to determine the values we are trying to find.
from .predicate import (
    CloneableWithNewSource,
    PredicateResult,
    ValuePredicate)

from .sequenced_predicate_result import (
    SequencedPredicateResult,
    SequencedPredicateResultBuilder)

from .keyed_predicate_result import (
    KeyedPredicateResult,
    KeyedPredicateResultBuilder)

from .path_result import (
    IndexBoundsError,
    MissingPathError,
    PathResult,
    PathValueResult,
    TypeMismatchError,
    UnexpectedPathError)

from .path_predicate_result import (
    PathPredicateResult,
    PathPredicateResultBuilder,
    PathPredicateResultCandidate)

from .path_predicate import (
    DONT_ENUMERATE_TERMINAL,
    PathPredicate)

from .path_transforms import (
    FieldDifference)

from .base_binary_predicate import (
    BinaryPredicate)

from .simple_binary_predicate import (
    SimpleBinaryPredicate,
    SimpleBinaryPredicateFactory,
    StandardBinaryPredicate,          # deprecated
    StandardBinaryPredicateFactory,   # deprecated
    DICT_EQ,
    DICT_NE,
    LIST_EQ,
    LIST_NE,
    NUM_LE,
    NUM_GE,
    NUM_EQ,
    NUM_NE,
    STR_SUBSTR,
    STR_EQ,
    STR_NE)

from .matches_predicate import (
    DictMatchesPredicate,
    ListMatchesPredicate,
    DICT_MATCHES,
    LIST_MATCHES)

from .binary_predicate import (
    ContainsPredicate,
    DictSubsetPredicate,
    DifferentPredicate,
    EquivalentPredicate,
    ListMembershipPredicate,
    ListSubsetPredicate,

    CONTAINS,
    DIFFERENT,
    EQUIVALENT,

    DICT_SUBSET,
    LIST_MEMBER,
    LIST_SIMILAR,
    LIST_SUBSET)

from .path_predicate_helpers import (
    PathContainsPredicate,
    PathElementsContainPredicate,
    PathEqPredicate)

# The logic_predicate module adds and/or logic aggregation
# to return composite results based on applying multiple predicates.
from .logic_predicate import (
    AND,
    IF,
    NOT,
    OR,
    ConditionalPredicate,
    ConjunctivePredicate,
    DisjunctivePredicate,
    NegationPredicate)

# The map_predicate module contains a mapper that maps a predicate over an
# object list.
from .map_predicate import (
    MapPredicate,
    MapPredicateResult,
    MapPredicateResultBuilder,
    ObjectResultMapAttempt)

from .cardinality_predicate import (
    CardinalityPredicate,
    CardinalityResult,
    ConfirmedCardinalityResult,

    FailedCardinalityResult,
    FailedCardinalityRangeResult,
    MissingValueCardinalityResult,
    UnexpectedValueCardinalityResult)

from .exception_predicate import (
    ExceptionMatchesPredicate
    )
