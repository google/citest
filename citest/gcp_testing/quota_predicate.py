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

"""Support for observing and verifying GCP available quota."""

import logging

from . import GceContractBuilder

from ..base import (
    JournalLogger,
    get_global_journal)

from ..json_predicate import (
    CompositePredicateResultBuilder,
    DONT_ENUMERATE_TERMINAL,
    NUM_GE,
    NUM_LE,
    EQUIVALENT,
    FieldDifference,
    PathPredicate,
    PathValue,
    PathValueResult,
    ValuePredicate)


class QuotaPredicate(ValuePredicate):
  """Specialization to test GCP quota availability.

  The quota metric values dont appear to be officially enumerated in docs.

  For a list of current project metrics, try the following command:
  gcloud compute project-info describe | grep metric | sed 's/metric: //g'

  SNAPSHOTS
  NETWORKS
  FIREWALLS
  IMAGES
  STATIC_ADDRESSES
  ROUTES
  FORWARDING_RULES
  TARGET_POOLS
  HEALTH_CHECKS
  IN_USE_ADDRESSES
  TARGET_INSTANCES
  TARGET_HTTP_PROXIES
  URL_MAPS
  BACKEND_SERVICES
  INSTANCE_TEMPLATES
  TARGET_VPN_GATEWAYS
  VPN_TUNNELS
  ROUTERS
  TARGET_HTTPS_PROXIES
  SSL_CERTIFICATES
  SUBNETWORKS


  For a list of current regional metrics, try the following command:
  gcloud compute regions describe us-east1 | grep metric | sed 's/metric: //g'

  CPUS
  DISKS_TOTAL_GB
  STATIC_ADDRESSES
  IN_USE_ADDRESSES
  SSD_TOTAL_GB
  LOCAL_SSD_TOTAL_GB
  INSTANCE_GROUPS
  INSTANCE_GROUP_MANAGERS
  INSTANCES
  AUTOSCALERS

  """

  @property
  def minimum_quota(self):
    """The expected quota"""
    return self.__minimum_quota

  def __init__(self, minimum_quota):
    """Constructor.

    Args:
      minimum_quota [dict of number]: Dictionary of resource metric names
         and quota they require. The predicate will check that the available
         resource quota can accomodate the additional number in this dict.
    """
    self.__minimum_quota = dict(minimum_quota)
    self.__logger = logging.getLogger(__name__)
    self.__diff = FieldDifference('limit', 'usage')

  def __repr__(self):
    return 'minimum_metrics: {0!r}'.format(self.__minimum_quota)

  def __call__(self, value):
    """Implements ValuePredicate.

    Args:
       values: [array of dict] A list of dictionary resource quota descriptions
          following the format returned described by the "quotas" attribute of
          https://cloud.google.com/compute/docs/reference/latest/projects#resource
    """
    builder = CompositePredicateResultBuilder(self)
    dictified = {elem['metric']: elem for elem in value}

    bad_metrics = []
    for metric, expect in self.__minimum_quota.items():
      found = dictified.get(metric)
      if found is None:
        bad_metrics.append(metric)
        builder.append_result(
            PathValueResult(source=None, target_path='metric',
                            path_value=PathValue('', value),
                            valid=False, pred=EQUIVALENT(metric),
                            comment='Missing metric value.'))
        continue
      pred = PathPredicate('', pred=NUM_GE(expect), transform=self.__diff)
      result = pred(found)
      builder.append_result(result)
      if not result:
        bad_metrics.append(metric)

    if bad_metrics:
      builder.comment = 'Insufficient {0}.'.format(' and '.join(bad_metrics))
      valid = False
    else:
      valid = True
      builder.comment = 'Satisfied all {0} metrics.'.format(
          len(self.__minimum_quota))

    return builder.build(valid)

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(
        entity, 'Minimum', self.__minimum_quota)

  def __eq__(self, pred):
    return (self.__class__ == pred.__class__
            and self.__minimum_quota == pred.minimum_quota)


def make_quota_contract(gcloud_agent, project_quota, regions):
  """Create a json_contract.Contract that checks GCP quota.

  Args:
    gcloud_agent: [GCloudAgent] Observation agent on the desired project.
    project_quota: [dict] Minimum desired values keyed by quota metric for
       the observed project.
    regions: [array of (name, dict) tuple]: A list of regions and their
       individual quotas to check.

  Returns:
    json_contract.Contract that will test the project quota.
  """
  quotas_field = 'quotas' + DONT_ENUMERATE_TERMINAL
  builder = GceContractBuilder(gcloud_agent)
  (builder.new_clause_builder('Has Project Quota')
   .inspect_resource('project-info', None)
   .add_constraint(PathPredicate(quotas_field, QuotaPredicate(project_quota))))
  for region, quota in regions:
    (builder.new_clause_builder('Has Regional Quota for {0}'.format(region))
     .inspect_resource('regions', None, extra_args=[region])
     .add_constraint(PathPredicate(quotas_field, QuotaPredicate(quota))))

  return builder.build()


def verify_quota(title, gcloud_agent, project_quota, regions):
  """Verify that the observed GCP project has sufficient quota.

  Args:
    title: [string] What the quota is for, for logging purposes only.
    gcloud_agent: [GCloudAgent] Observation agent on the desired project.
    project_quota: [dict] Minimum desired values keyed by quota metric for
       the observed project.
    regions: [array of (name, dict) tuple]: A list of regions and their
       individual quotas to check.

  Returns:
    json_contract.ContractVerifyResult against the quota check.
  """
  contract = make_quota_contract(gcloud_agent, project_quota, regions)
  verify_results = None
  context_relation = 'ERROR'

  try:
    JournalLogger.begin_context(title)
    verify_results = contract.verify()
    context_relation = 'VALID' if verify_results else 'INVALID'
  finally:
    if verify_results is not None:
      journal = get_global_journal()
      if journal is not None:
        journal.store(verify_results)
    JournalLogger.end_context(relation=context_relation)

  return verify_results
