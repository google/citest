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


"""Helper functions for creating authenticated GCP service clients."""

import logging
import httplib2

from apiclient import discovery
from googleapiclient.errors import HttpError
from oauth2client.service_account import ServiceAccountCredentials

from .. import json_contract as jc


PLATFORM_READ_ONLY_SCOPE = (
    'https://www.googleapis.com/auth/cloud-platform.read-only'
    )
PLATFORM_FULL_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'


def build_authenticated_service(name, version, scopes, credentials_path):
  """Create an authenticated service client instance.

  Args:
    name: [String] The name of the service.
    version: [String] The service API version.
    scopes: [String] The credentials OAuth2 scopes.
    credentials_path: [String] Path to JSON file containing GCP secrets.
  Returns:
    A Resource object with methods for interacting with the service.
  """
  logger = logging.getLogger(__name__)
  logger.info('Authenticating %s %s', name, version)
  credentials = ServiceAccountCredentials.from_json_keyfile_name(
      credentials_path, scopes=scopes)

  logger.info('Constructing %s service...', name)
  http = credentials.authorize(httplib2.Http())
  return discovery.build(name, version, http=http)


class GoogleAgentObservationFailureVerifier(jc.ObservationFailureVerifier):
  """An ObservationVerifier that expects specific errors from stderr."""

  def __init__(self, title, error_regex):
    """Constructs the clause with the acceptable error regex.

    Args:
      title: Verifier name for reporting purposes only.
      error_regex: Regex pattern for errors we're looking for.
    """
    super(GoogleAgentObservationFailureVerifier, self).__init__(title)
    self.__error_regex = error_regex

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotable interface."""
    snapshot.edge_builder.make_control(entity, 'Regex', self.__error_regex)
    super(GoogleAgentObservationFailureVerifier, self).export_to_json_snapshot(
        snapshot, entity)

  def _error_comment_or_none(self, error):
    if (isinstance(error, HttpError)
        and error.match_regex(self.__error_regex)):
      return 'Error matches {0}'.format(self.__error_regex)
