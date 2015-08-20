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


import logging
import time

from ..base.scribe import Scribable
from ..base.scribe import Scribe
from . import predicate
from . import observer as ob
from . import observation_verifier as ov


class ContractClauseVerifyResult(predicate.PredicateResult):
  @property
  def clause(self):
    return self._clause

  @property
  def verify_results(self):
    return self._verify_results

  @property
  def enumerated_summary_message(self):
    verify_summary = self._verify_results.enumerated_summary_message
    if verify_summary:
      verify_summary = '  {0}'.format(verify_summary.replace('\n', '\n  '))
    else:
      verify_summary = '  <no further data>'

    return '* Clause {title} is {ok}\n{verify}'.format(
        title=self.clause.title,
        ok='GOOD' if self else 'BAD',
        verify=verify_summary)

  def __init__(self, valid, clause, verify_results):
    super(ContractClauseVerifyResult, self).__init__(valid)
    self._clause = clause
    self._verify_results = verify_results

  def __eq__(self, result):
    return  (super(ContractClauseVerifyResult, self).__eq__(result)
             and self._clause == result._clause
             and self._verify_results == result._verify_results)

  def __str__(self):
    return 'Clause {0}:\n  {1}'.format(
        self._clause.title,
        self._verify_results.enumerated_summary_message)

  def _make_scribe_parts(self, scribe):
    summary = 'Verified' if self._verify_results else 'FAILED'
    relation = scribe.part_builder.determine_verified_relation(
        self._verify_results)

    parts = [
        scribe.part_builder.build_input_part(
          'Clause', self._clause, summary=self._clause.title),
        scribe.part_builder.build_nested_part(
          'Results', self._verify_results, summary=summary, relation=relation)]
    inherited = super(ContractClauseVerifyResult, self)._make_scribe_parts(
        scribe)
    return parts + inherited


class ContractClause(predicate.ValuePredicate):
  """Specifies how to obtain state information and expectations on it.

  Attributes:
    observer: The ObjectObserver used to collect Observation.
      This can be bound after construction, but can only be set once.
    verifier: The ObservationVerifier used to verify the observed state.
      This can be bound after construction, but can only be set once.
  """
  @property
  def observer(self):
    return self._observer

  @property
  def verifier(self):
    return self._verifier

  @property
  def title(self):
    return self._title

  def __str__(self):
    return 'Clause {0}  verifier={1}'.format(self._title, self._verifier)

  def _make_scribe_parts(self, scribe):
    return [
        scribe.build_part('Title', self._title),
        scribe.part_builder.build_mechanism_part('Observer', self._observer),
        scribe.part_builder.build_mechanism_part('Verifier', self._verifier)]

  def __init__(self, title, observer=None, verifier=None,
               retryable_for_secs=0):
    """Construct clause.

    Args:
      title: string title for logging clause.
      observer: An ObjectObserver for supplying data to verify.
      verifier: A ObservationVerifier on the observer's Observations.
      retryable_for_secs: If > 0, then how long to continue retrying
        when a verification attempt fails.
    """
    self._title = title
    self._observer = observer
    self._verifier = verifier
    self._retryable_for_secs = retryable_for_secs
    self.logger = logging.getLogger(__name__)

  def verify(self):
    """Attempt to make an observation and verify it.

    This call will repeatedly attempt to observe new data and verify it
    until either the verification passes, or it times out base on
    the retryable_for_secs specified in the constructor.

    Returns:
      ContractClauseVerifyResult with details.
    """
    self.logger.debug('Verifying Contract: %s', self._title)
    start_time = time.time()
    end_time = start_time + self._retryable_for_secs

    while True:
      clause_result = self.verify_once()
      if clause_result:
        break

      now = time.time()
      if end_time <= now:
        if end_time > start_time:
          self.logger.debug(
            'Giving up verifying %s after %d of %d secs.',
            self._title, end_time - start_time, self._retryable_for_secs)
        break

      secs_remaining = end_time - now
      sleep = min(secs_remaining, min(5, self._retryable_for_secs / 10))
      self.logger.debug(
        '%s not yet satisfied with secs_remaining=%d. Retry in %d secs\n%s',
        self._title, secs_remaining, sleep, clause_result)
      time.sleep(sleep)

    summary = clause_result.enumerated_summary_message
    ok_str = 'OK' if clause_result else 'FAILED'
    self.logger.debug('ContractClause %s: %s\n%s',
                      ok_str, self._title, summary)
    return clause_result

  def verify_once(self):
    if not self._observer:
      raise Exception(
        'No ObjectObserver bound to clause {0!r}'.format(self._title))
    if not self._verifier:
      raise Exception(
        'No ObservationVerifier bound to clause {0!r}'.format(self._title))

    observation = ob.Observation()
    self._observer.collect_observation(observation)

    verify_result = self._verifier(observation)
    return ContractClauseVerifyResult(
        verify_result.__nonzero__(), self, verify_result)


class ContractClauseBuilder(object):
  @property
  def verifier_builder(self):
    return self._verifier_builder

  @verifier_builder.setter
  def verifier_builder(self, builder):
    self._verifier_builder = builder

  @property
  def retryable_for_secs(self):
    return self._retryable_for_secs

  @retryable_for_secs.setter
  def retryable_for_secs(self, secs):
    self._retryable_for_secs = secs

  @property
  def observer(self):
    return self._observer

  @observer.setter
  def observer(self, observer):
    if self._observer != None:
      raise ValueError('Observer was already set on clause')
    self._observer = observer

  def __init__(self, title, observer=None, verifier_builder=None,
               retryable_for_secs=0):
    self._title = title
    self._observer = observer
    self._verifier_builder = (verifier_builder
                              or ov.ObservationVerifierBuilder(title))
    self._retryable_for_secs = retryable_for_secs

  def build(self):
    return ContractClause(
        title=self._title,
        observer=self._observer,
        verifier=self._verifier_builder.build(),
        retryable_for_secs=self._retryable_for_secs)


class ContractVerifyResult(predicate.PredicateResult):
  @property
  def enumerated_summary_message(self):
    return '\n'.join(
        [c.enumerated_summary_message for c in self._clause_results])

  @property
  def clause_results(self):
    return self._clause_results

  def __init__(self, valid, clause_results):
    super(ContractVerifyResult, self).__init__(valid)
    self._clause_results = clause_results

  def __eq__(self, result):
    return (super(ContractVerifyResult, self).__eq__(result)
            and self._clause_results == result._clause_results)

  def __str__(self):
    str_ok = 'OK' if self else 'FAILED'
    return 'Contract {0}\n{1}'.format(
        str_ok,
        '\n'.join(
            [c.enumerated_summary_message for c in self._clause_results]))

  def _make_scribe_parts(self, scribe):
    summary = 'Verified' if self else 'FAILED'
    relation = scribe.part_builder.determine_verified_relation(self)

    parts = [
        scribe.part_builder.build_nested_part(
        'Clause Results', self._clause_results,
        summary=summary, relation=relation)]
    inherited = super(ContractVerifyResult, self)._make_scribe_parts(scribe)
    return parts + inherited


class Contract(Scribable):
  """A contract holds a collection of ContractClause.

  Attributes:
    clauses: A list of ContractClause.
  """
  @property
  def clauses(self):
    return self._clauses

  def __init__(self):
    self._clauses = []

  def _make_scribe_parts(self, scribe):
    return [scribe.part_builder.build_control_part('Clauses', self._clauses)]

  def add_clause(self, clause):
    """Adds a clause to the contract.

    Args:
      clause: A ContractClause.
    """
    self._clauses.append(clause)

  def verify(self):
    """Verify the clauses in the contract are currently satisified.

    Returns:
     True if success, False if not.
    """
    valid = True
    all_results = []
    for clause in self._clauses:
      clause_results = clause.verify()
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
    """
    self._clause_factory = (
        clause_factory
        or (lambda title, retryable_for_secs:
           ContractClauseBuilder(title, retryable_for_secs)))
    self._builders = []

  def new_clause_builder(self, title, retryable_for_secs=0):
    """Add new clause to contract from which specific constraints can be added.

    Args:
      title: The name of the contract is used for reporting context only.
      retryable_for_secs: If > 0 then this clause is permitted to
          initially fail, but should eventually be met within the given
          time period.

    Returns:
      A new ClauseBuilder created with the factory bound in the constructor.
    """
    builder = self._clause_factory(title, retryable_for_secs=retryable_for_secs)
    self._builders.append(builder)
    return builder

  def build(self):
    """Creates a new contract with the added clauses."""
    contract = Contract()
    for builder in self._builders:
        contract.add_clause(builder.build())
    return contract
