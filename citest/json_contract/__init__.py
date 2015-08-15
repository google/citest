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


# This module is intended to support the higher level json_contract.* modules.
# To that end, the lookups populate PredicateResult objects rather than just
# returning values, so are heavier weight that would be otherwise.
from path import PathValue


# json_contract.lookup_predicate provides support for extracting field values
# from. It takes a simplistic path/value look at structured JSON
# and will traverse a specified "path" to extract out the first value it
# finds. In the case of a intermediate node being a list, it will walk the
# list elements until it ultimately finds a matching value.
from lookup_predicate import lookup_path


# json_contract.predicate provides a mechanism using callable objects
# to validate a a value. It is used to support the finder
# module to specify how to determine the values we are trying to find.
from predicate import (
    CompositePredicateResult,
    CompositePredicateResultBuilder,
    PredicateResult,
    ValuePredicate)


from path_predicate_result import (
    JsonFoundValueResult,
    JsonMissingPathResult,
    JsonTypeMismatchResult)


from path_predicate import PathPredicate


from path_predicate2 import(
    PathEqPredicate,
    PathContainsPredicate,
    PathElementsContainPredicate)


from binary_predicate import (
    CONTAINS,
    DIFFERENT,
    EQUIVALENT,
    STR_EQ,
    STR_NE,
    STR_SUBSTR,
    DICT_EQ,
    DICT_NE,
    DICT_SUBSET,
    LIST_EQ,
    LIST_NE,
    LIST_SUBSET,
    NUM_LE,
    NUM_EQ,
    NUM_NE,
    NUM_GE,
    BinaryPredicate,
    StandardBinaryPredicate)


# The logic_predicate module adds and/or logic aggregation
# to return composite results based on applying multiple predicates.
from logic_predicate import (
    ConjunctivePredicate,
    DisjunctivePredicate)


# The quantification_predicate module adds Existential and Universal
# quantification to apply a predicate to a collection of objects and
# expect some or all of the objects to be valid.
from quantification_predicate import UniversalOrExistentialPredicate
from quantification_predicate2 import (
    EXISTS_CONTAINS,
    EXISTS_EQ,
    EXISTS_NE,
    ALL_CONTAINS,
    ALL_EQ,
    ALL_NE)


# The map_predicate module contains a mapper that maps a predicate over an
# object list.
from map_predicate import (
    MapPredicate,
    MapPredicateResult,
    MapPredicateResultBuilder,
    ObjectResultMapAttempt)


# The cardinality_predicate module contains a predicate that
# uses a mapper, succeeding if the cardinality of good results is within
# a range.
from cardinality_predicate import (
    CardinalityPredicate)


# The observer module contains support for specifying observers and making
# observations onto a system to collect the data supporting verification.
from observer import (
    ObjectObserver,
    Observation)


# The verifier module provides support for verifying observations meet
# expectations.
from observation_verifier import (
    ObservationVerifier,
    ObservationVerifierBuilder,
    ObservationVerifyResultBuilder,
    ObservationVerifyResult)


from value_observation_verifier import (
    ValueObservationVerifier,
    ValueObservationVerifierBuilder)


from observation_failure import (
    ObservationFailedError,
    ObservationFailureVerifier)


# The contract module provides a means to specify and verify contracts on
# expected system state, and how to collect that state using observations.
from contract import (
    Contract,
    ContractBuilder,
    ContractClause,
    ContractClauseBuilder)
