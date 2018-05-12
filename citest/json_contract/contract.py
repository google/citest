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


"""Provides supporting classes for specifying and verifying Contracts.

A contract specifies a list of observations and their expected properties.
Each member of this list is called a Clause. The expectations are typically
specified as ObservationVerifiers which may specify values that are expected
(or not), or perhaps properties of the observation itself, such as errors
attempting to make it (e.g. the observed resource does not exist).
"""


import logging
import time

from citest.base import JournalLogger
from citest.base import JsonSnapshotableEntity
import citest.json_predicate.predicate as predicate
from . import observer as ob
from . import observation_verifier as ov


class ContractClauseVerifyResult(predicate.PredicateResult):
  """Represents the analysis result of verifying a contract clause."""
  @property
  def clause(self):
    """The clause that was verified."""
    return self.__clause

  @property
  def verify_results(self):
    """The results from applying the clause verifier."""
    return self.__verify_results

  @property
  def enumerated_summary_message(self):
    """Human readable verification result summary string."""
    verify_summary = self.__verify_results.enumerated_summary_message
    if verify_summary:
      verify_summary = '  {0}'.format(verify_summary.replace('\n', '\n  '))
    else:
      verify_summary = '  <no further data>'

    return '* Clause {title} is {ok}\n{verify}'.format(
        title=self.clause.title,
        ok='GOOD' if self else 'BAD',
        verify=verify_summary)

  def __init__(self, valid, clause, verify_results, **kwargs):
    """Constructor.

    Args:
      valid: [bool] Whether the verification succeeded or not.
      clause: [ContractClause] The clause being validated
      verify_results: [ObservationVerifyResult] The result of verifying
         the clause (against an observation).

      See base class (PredicateResult) for additional kwargs.
    """
    super(ContractClauseVerifyResult, self).__init__(valid, **kwargs)
    self.__clause = clause
    self.__verify_results = verify_results

  def __eq__(self, result):
    return  (super(ContractClauseVerifyResult, self).__eq__(result)
             and self.__clause == result.clause
             and self.__verify_results == result.verify_results)

  def __str__(self):
    str_ok = 'OK' if self else 'FAILED'
    return 'Clause {title} {ok}'.format(
        title=self.__clause.title,
        ok=str_ok)

  def __repr__(self):
    return '{0!r} clause={1!r} verify_results={2!r}'.format(
        super(ContractClauseVerifyResult, self).__repr__(),
        self.__clause, self.__verify_results)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    entity.add_metadata('_title',
                        'Verification of "{0}"'.format(self.__clause.title))

    relation = builder.determine_valid_relation(self.__verify_results)
    builder.make_control(entity, 'Clause', self.__clause)
    builder.make(entity, 'Results', self.__verify_results, relation=relation)
    super(ContractClauseVerifyResult, self).export_to_json_snapshot(
        snapshot, entity)


class ContractClause(predicate.ValuePredicate):
  """Specifies how to obtain state information and expectations on it."""
  @property
  def observer(self):
    """The ObjectObserver used to collect the Observation."""
    return self.__observer

  @property
  def verifier(self):
    """The ObservationVerifier used to verify the observed state."""
    return self.__verifier

  @property
  def title(self):
    """The name of the clause for reporting purposes."""
    return self.__title

  def __str__(self):
    return 'Clause {0}  verifier={1}'.format(self.__title, self.__verifier)

  def __repr__(self):
    return '{0}  title={1} verifier={2!r}'.format(
        super(ContractClause, self).__repr__(), self.__title, self.__verifier)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    entity.add_metadata('_title', self.__title)
    snapshot.edge_builder.make(entity, 'Title', self.__title)
    snapshot.edge_builder.make_mechanism(entity, 'Observer', self.__observer)
    snapshot.edge_builder.make_mechanism(entity, 'Verifier', self.__verifier)

  def __init__(self, title, observer=None, verifier=None, **kwargs):
    """Construct clause.

    Args:
      title: string title for logging clause.
      observer: An ObjectObserver for supplying data to verify.
      verifier: A ObservationVerifier on the observer's Observations.
      retryable_for_secs: If > 0, then how long to continue retrying
        when a verification attempt fails.
    """
    self.logger = logging.getLogger(__name__)
    self.__retryable_for_secs = kwargs.pop('retryable_for_secs', 0)
    self.__title = title
    self.__observer = observer
    self.__verifier = verifier
    super(ContractClause, self).__init__(**kwargs)

  def verify(self, context):
    """Attempt to make an observation and verify it.

    This call will repeatedly attempt to observe new data and verify it
    until either the verification passes, or it times out base on
    the retryable_for_secs specified in the constructor.

    Args:
      context: Runtime citest execution context may contain operation status
         and other testing parameters used by downstream verifiers.

    Returns:
      ContractClauseVerifyResult with details.
    """
    JournalLogger.begin_context(
        'Verifying ContractClause: {0}'.format(self.__title))

    context_relation = 'ERROR'
    try:
      JournalLogger.delegate("store", self, _title='Clause Specification')

      result = self.__do_verify(context)
      context_relation = 'VALID' if result else 'INVALID'
    finally:
      JournalLogger.end_context(relation=context_relation)
    return result

  def __do_verify(self, context):
    """Helper function that implements the clause verification policy.

    We will periodically attempt to verify the clause until we succeed
    or give up trying. Each individual iteration attempt is performed
    by the verify_once method.

    Args:
      context: Runtime citest execution context.
    Returns:
      VerifyClauseResult specifying the final outcome.
    """

    # self.logger.debug('Verifying Contract: %s', self.__title)
    start_time = time.time()
    end_time = start_time + self.__retryable_for_secs

    while True:
      clause_result = self.verify_once(context)
      if clause_result:
        break

      now = time.time()
      if end_time <= now:
        if end_time > start_time:
          self.logger.debug(
              'Giving up verifying %s after %r of %r secs.',
              self.__title, end_time - start_time, self.__retryable_for_secs)
        break

      secs_remaining = end_time - now

      # This could be a bounded exponential backoff, but we probably
      # want to have an idea of when it actually becomes available so keep low.
      # But if we are going to wait a long time, then dont poll very frequently.
      # The numbers here are arbitrary otherwise.
      #
      # 1/10 total time or 5 seconds if that is pretty long,
      # but no less than 1 second unless there is less than 1 second left.
      sleep = min(secs_remaining, min(5, max(1, self.__retryable_for_secs / 10)))
      self.logger.debug(
          '%s not yet satisfied with secs_remaining=%r. Retry in %r\n%s',
          self.__title, secs_remaining, sleep, clause_result)
      time.sleep(sleep)

    summary = clause_result.enumerated_summary_message
    ok_str = 'OK' if clause_result else 'FAILED'
    JournalLogger.delegate(
        "store", clause_result,
        _title='Validation Analysis of "{0}"'.format(self.__title))
    self.logger.debug('ContractClause %s: %s\n%s',
                      ok_str, self.__title, summary)
    return clause_result

  def verify_once(self, context):
    """Make a single attempt to collect an observation and verify it.

    Args:
      context: Runtime citest execution context.

    Raises:
      ValueError of the clause is not yet fully specified.

    Returns:
      ContractClauseVerifyResult from verifying the observation
    """
    if not self.__observer:
      raise ValueError(
          'No ObjectObserver bound to clause {0!r}'.format(self.__title))
    if not self.__verifier:
      raise ValueError(
          'No ObservationVerifier bound to clause {0!r}'.format(self.__title))

    observation = ob.Observation()
    self.__observer.collect_observation(context, observation)

    verify_result = self.__verifier(context, observation)
    return ContractClauseVerifyResult(
        verify_result.__nonzero__(), self, verify_result)


class ContractClauseBuilder(object):
  """A helper class for constructing a ContractClause."""

  @property
  def verifier_builder(self):
    """Builds the clause verifier."""
    return self.__verifier_builder

  @verifier_builder.setter
  def verifier_builder(self, builder):
    """Sets the builder used to construct the clause verifier."""
    self.__verifier_builder = builder

  @property
  def retryable_for_secs(self):
    """How long to continue validating the clause until it holds.

    This does not specify the interval for retrying. Only the elapsed time.
    """
    return self.__retryable_for_secs

  @retryable_for_secs.setter
  def retryable_for_secs(self, secs):
    """Set how long to continue validating the clause until it holds."""
    self.__retryable_for_secs = secs

  @property
  def observer(self):
    """The observer used to gather the required data to verify."""
    return self.__observer

  @observer.setter
  def observer(self, observer):
    """Sets the observer used to gather the required data to verify."""
    if self.__observer != None:
      raise ValueError('Observer was already set on clause')
    self.__observer = observer

  def __init__(self, title, observer=None, verifier_builder=None, **kwargs):
    """Constructor.

    Args:
      title: [string] The name of the clause.
      observer: [Observer] The observer used to collect verification data.
      verifier_builder: Builds the clause verifier.
      retryable_for_secs: [int] How long the clause can continue colllecting
         observation data until it can be confirmed to hold.
    """
    strict = kwargs.pop('strict', False)
    if strict:
      logger = logging.getLogger(__name__)
      logger.warning('Strict flag is DEPRECATED in %s', title)

    self.__retryable_for_secs = kwargs.pop('retryable_for_secs', 0)
    self.__title = title
    self.__observer = observer
    self.__verifier_builder = (verifier_builder
                               or ov.ObservationVerifierBuilder(title, warn_nested=False))

  def build(self):
    """Build the clause from the builder specification."""
    return ContractClause(
        title=self.__title,
        observer=self.__observer,
        verifier=self.__verifier_builder.build(),
        retryable_for_secs=self.__retryable_for_secs)


class ContractVerifyResult(predicate.PredicateResult):
  """Represents the analysis results of verifying a contract and its clauses.
  """
  @property
  def enumerated_summary_message(self):
    """Human readable summary of the verification results."""
    str_ok = 'OK' if self else 'FAILED'
    clauses = '\n'.join(['  * Clause {title} is {ok}'
                         .format(title=c.clause.title,
                                 ok='OK' if c.valid else 'BAD')
                         for c in self.__clause_results])
    return 'Contract {ok}\n{clauses}'.format(ok=str_ok, clauses=clauses)

  @property
  def clause_results(self):
    """The aggregated results of verifying each of the contract's clauses."""
    return self.__clause_results

  def __init__(self, valid, clause_results, **kwargs):
    """Constructor.

    Args:
      valid: [bool] Whether the contract validated or not.
      clause_results: [PredicateResult] The aggregated results of validating
         each of the clauses is usually an IndexedPredicateResult.

      See base class (PredicateResult) for additional kwargs.
    """
    super(ContractVerifyResult, self).__init__(valid, **kwargs)
    self.__clause_results = clause_results

  def __eq__(self, result):
    return (super(ContractVerifyResult, self).__eq__(result)
            and self.__clause_results == result.clause_results)

  def __str__(self):
    return self.enumerated_summary_message

  def __repr__(self):
    return '{0} clause_results={1!r}'.format(
        super(ContractVerifyResult, self).__repr__(), self.__clause_results)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    relation = snapshot.edge_builder.determine_valid_relation(self)
    snapshot.edge_builder.make(
        entity, 'Clause Results', self.__clause_results, relation=relation)
    super(ContractVerifyResult, self).export_to_json_snapshot(snapshot, entity)


class Contract(JsonSnapshotableEntity):
  """A contract holds a collection of ContractClause.

  Attributes:
    clauses: A list of ContractClause.
  """
  @property
  def clauses(self):
    """The list of ContractClause."""
    return self.__clauses

  def __init__(self):
    self.__clauses = []

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    snapshot.edge_builder.make_control(entity, 'Clauses', self.__clauses)

  def add_clause(self, clause):
    """Adds a clause to the contract.

    Args:
      clause: A ContractClause.
    """
    self.__clauses.append(clause)

  def verify(self, context):
    """Verify the clauses in the contract are currently satisified.

    Returns:
     True if success, False if not.
    """
    valid = True
    all_results = []
    for clause in self.__clauses:
      clause_results = clause.verify(context)
      all_results.append(clause_results)
      if not clause_results:
        valid = False

    return ContractVerifyResult(valid, all_results)


class ContractBuilder(object):
  """Acts as a clause factory to assemble clauses into contracts."""

  def __init__(self, clause_factory=None):
    """Constructs a new contract.

    Args:
      clause_factory: Factory function expects a string title
         and retryable_for_secs and returns a ClauseBuilder.
         It also takes a DEPRECATED strict flag. This is deprecated
         because in the future the strict flag will be on individual
         constraints added to the clause.
    """
    def default_clause_builder(
        title, retryable_for_secs=0, strict=False, **kwargs):
      return ContractClauseBuilder(title, retryable_for_secs, strict=strict,
                                   **kwargs)
    self.__clause_factory = clause_factory or default_clause_builder
    self.__builders = []

  def new_clause_builder(self, title, retryable_for_secs=0, strict=False,
                         **kwargs):
    """Add new clause to contract from which specific constraints can be added.

    Args:
      title: The name of the contract is used for reporting context only.
      retryable_for_secs: If > 0 then this clause is permitted to
          initially fail, but should eventually be met within the given
          time period.
      strict: DEPRECATED strict flag. This is deprecated because in the future
          strict will be on individual constraints added to the clause.

    Returns:
      A new ClauseBuilder created with the factory bound in the constructor.
    """
    builder = self.__clause_factory(
        title, retryable_for_secs=retryable_for_secs, strict=strict,
        **kwargs)
    self.__builders.append(builder)
    return builder

  def build(self):
    """Creates a new contract with the added clauses."""
    contract = Contract()
    for builder in self.__builders:
      contract.add_clause(builder.build())
    return contract
