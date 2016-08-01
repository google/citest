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


"""Support for notifying and detecting failures in observers."""

from ..json_predicate import map_predicate
from ..json_predicate import predicate
from . import observation_verifier as ov
from . import observer


class ObservationFailedError(predicate.PredicateResult):
  """Denotes a PredicateResult for a failure to make an observation.

  This is intended for ObservationVerifier where the attempt to make an
  observation failed as opposed to a successful observation whose content
  was not as expected.
  """

  @property
  def failures(self):
    """The failures encountered while trying to make the observation."""
    return self.__failures

  def __init__(self, failures, valid=False):
    super(ObservationFailedError, self).__init__(valid)
    self.__failures = failures

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    super(ObservationFailedError, self).export_to_json_snapshot(
        snapshot, entity)
    snapshot.edge_builder.make(entity, 'Failures', self.__failures)

  def __str__(self):
    return 'Observation has failures: {0}'.format(
        ','.join([str(x) for x in self.__failures]))

  def __eq__(self, event):
    return (super(ObservationFailedError, self).__eq__(event)
            and observer.Observation.error_lists_equal(
                self.__failures, event.failures))


class ObservationFailureVerifier(ov.ObservationVerifier):
  """An ObservationVerifier that expects specific errors in an Observation"""

  def __init__(self, title):
    """Constructs the clause with the expected error.

    Args:
      title: Verifier name for reporting purposes only.
    """
    super(ObservationFailureVerifier, self).__init__(title)

  def _error_comment_or_none(self, error):
    """Determine if the error is expected or not.

    Args:
      error: An error among the observation.errors

    Returns:
      None if the error is not expected, otherwise a comment string.
          The comment string will propagate back our the results.
    """
    raise NotImplementedError(
        '{0}._error_comment_or_none not implemented.'.format(self.__class__))

  def _error_not_found_comment(self, observation):
    """Provide a comment string indicating no suitable errors were found."""
    return ("Observation had no errors."
            if not observation.errors else "Expected error was not found.""")

  def __call__(self, observation):
    valid = False
    error = None
    for error in observation.errors:
      comment = self._error_comment_or_none(error)
      if comment != None:
        valid = True
        break

    if valid:
      result = ObservationFailedError(valid=True, failures=[error])
      map_attempt = map_predicate.ObjectResultMapAttempt(observation, result)
      good_results = [map_attempt]
      bad_results = []
    else:
      comment = self._error_not_found_comment(observation)
      result = predicate.PredicateResult(valid=False, comment=comment)
      map_attempt = map_predicate.ObjectResultMapAttempt(observation, result)
      good_results = []
      bad_results = [map_attempt]

    return ov.ObservationVerifyResult(
        valid=valid, observation=observation,
        good_results=good_results, bad_results=bad_results,
        failed_constraints=[], comment=comment)
