# Copyright 2017 Google Inc. All Rights Reserved.
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

"""Implements an Agent that interacts with Google App Engine."""

from .gcp_agent import GcpAgent


APPENGINE_READ_ONLY_SCOPE = 'https://www.googleapis.com/auth/cloud-platform.readonly'
APPENGINE_READ_WRITE_SCOPE = 'https://www.googleapis.com/auth/appengine.admin'
APPENGINE_FULL_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'


class GcpAppengineAgent(GcpAgent):
  """Agent that interacts with Google App Engine service."""

  @classmethod
  def scope_aliases(cls):
    """Implements GcpAgent interface."""
    return {
      'read-only': APPENGINE_READ_ONLY_SCOPE,
      'read-write': APPENGINE_READ_WRITE_SCOPE,
      'full': APPENGINE_FULL_SCOPE
    }

  @classmethod
  def default_discovery_name_and_version(cls):
    """Implements GcpAgent interface."""
    return 'appengine', 'v1'
