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

"""Implements an Agent that interacts with Google Compute."""

from .gcp_agent import GcpAgent


COMPUTE_READ_ONLY_SCOPE = 'https://www.googleapis.com/auth/compute.readonly'
COMPUTE_READ_WRITE_SCOPE = 'https://www.googleapis.com/auth/compute'
COMPUTE_FULL_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'


class GcpComputeAgent(GcpAgent):
  """Agent that interacts with Google Compute service."""

  @classmethod
  def scope_aliases(cls):
    """Implements GcpAgent interface."""
    return {
        'read-only': COMPUTE_READ_ONLY_SCOPE,
        'read-write': COMPUTE_READ_WRITE_SCOPE,
        'full': COMPUTE_FULL_SCOPE
    }

  @classmethod
  def default_discovery_name_and_version(cls):
    """Implements GcpAgent interface."""
    return 'compute', 'v1'

  def aggregated_list_resource(self, resource_type, **kwargs):
    """List the contents of the specified resource.

    This uses the aggregatedList variants (so the resource_type
    is either zonal or regional) rather than searching within
    a specific zone or region as list() would.

    Args:
      resource_type: [string] The name of the resource to list.
      kwargs: [kwargs] Additional parameters may be required depending
         on the resource type (such as zone, etc).

    Returns:
      A list of resources.
    """

    # We need to figure out where the data is in the response.
    # It is going to be in a dictionary key specific to the type,
    # which is the tail of the underlying method URL path so let's
    # look that up and use that in a transform to extract the items.
    path = (self.discovery_document['resources'][resource_type]
            ['methods']['aggregatedList']['path'])
    data_label = path.split('/')[-1]
    def transform(items):
      result = []
      for entry_values in items.values():
        data_values = entry_values.get(data_label, None)
        if data_values:
          result.extend(data_values)
      return result

    return self.list_resource(resource_type, method_variant='aggregatedList',
                              item_list_transform=transform, **kwargs)
