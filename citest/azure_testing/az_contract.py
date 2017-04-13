# Create the base agent for Azure CITest scenario

"""Support for specifying citest.json_contract.Contract on Azure resources."""

# Python modules
import json
import logging
import traceback

# CITest Modules
from .. import json_contract as jc
from ..json_predicate import JsonError
from ..service_testing import cli_agent


class AzObjectObserver(jc.ObjectObserver):
  """ Observe Az resources"""

  def __init__(self, az, args, filter=None):
    """Construct the observer.

    Attributes:
        az = AzCloudAgent instance to use.
        args: Commang-line arguments list to execute.
        filter: If provided, then use this to filter observations.
    """

    super(AzObjectObserver, self).__init__(filter)
    self.__az = az
    self.__args = args

  def __str__(self):
    return 'AzObjectObserver({0})'.format(self.__args)

  def collect_observation(self, context, observation, trace=True):
    args = context.eval(self.__args)
    az_response = self.__az.run(args, trace=trace)
    if not az_response.ok():
        observation.add_error(
            cli_agent.CliAgentRunError(self.__az, az_response))
        return []

    decoder = json.JSONDecoder()
    try:
      doc = decoder.decode(az_response.output)
      if not isinstance(doc, list):
        doc = [doc]
      observation.add_all_objects(doc)
      self.filter_all_objects_to_observation(context, doc, observation)
    except ValueError as vex:
        error = 'Invalid JSON in response: %s' % str(az_response)
        logging.getLogger(__name__).info('%s\n%s\n-----------------\n',
                                         error, traceback.format_exc())
        observation.add_error(JsonError(error, vex))
        return []

    return observation.objects

class AzClauseBuilder(jc.ContractClauseBuilder):
  """A ContractClause that facilitate observing the Azure state """

  def __init__(self, title, az, retryable_for_secs=0, strict=False):
    """Construct new clause.

    Attributes:
        title: The string title for the clause is only for reporting purposes.
        az: The AzAgent to make the observation for the clause to verify.
        retryable_for_secs: Number of seconds that observations can be retried
                            if their verification initially fails.
    strict: DEPRECATED flag indicating whether the clauses (added later)
        must be true for all objects (strict) or at least one (not strict).
        See ValueObservationVerifierBuilder for more information.
        This is deprecated because in the future this should be on a per
        constraint basis.
    """
    super(AzClauseBuilder, self).__init__(
        title=title, retryable_for_secs=retryable_for_secs)
    self.__az  = az
    self.__strict = strict

  def collect_resources(self, az_resource, command,
                        args=None, filter=None,
                        no_resources_ok=False):
    """Collect the Azure resources of a particular type.

    Attributes:
        az_resource: The az resource module name we're looking in (e.g. 'vm')
        command: The az command name to run (e.g. 'list')
        args: An array of strings containing the remaining az command parameters.
        filter: If provided, a filter to use for refining the collection.
        no_resources_ok: Whether or not the resource is required.
            If the resource is not required, 'resource not found' error is
            considered successful.
    """
    args = args or []
    cmd = self.__az.build_az_command_args(
        az_resource, command, args)

    self.observer = AzObjectObserver(self.__az, cmd)

    if no_resources_ok:
      error_verifier = cli_agent.CliAgentObservationFailureVerifier(
          title='"Not Found" permitted.',
          error_regex='(?:.* operation: Cannot find .*)|(?:.*\(.*NotFound\).*)')
      disjunction_builder = jc.ObservationVerifierBuilder(
          'Collect {0} or Not Found'.format(command))
      disjunction_builder.append_verifier(error_verifier)

      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command), strict=self.__strict)
      disjunction_builder.append_verifier_builder(
          collect_builder, new_term=True)
      self.verifier_builder.append_verifier_builder(
          disjunction_builder, new_term=True)
    else:
      collect_builder = jc.ValueObservationVerifierBuilder(
          'Collect {0}'.format(command), strict=self.__strict)
      self.verifier_builder.append_verifier_builder(collect_builder)

    return collect_builder

class AzContractBuilder(jc.ContractBuilder):

  def __init__(self, az):
    """Construct a new json_contract

    Args:
        az: The Azure Agent to use for communication with Azure
    """
    super(AzContractBuilder, self).__init__(
        lambda title, retryable_for_secs=0, strict=False:
        AzClauseBuilder(
            title, az=az,
            retryable_for_secs=retryable_for_secs, strict=strict)
    )
