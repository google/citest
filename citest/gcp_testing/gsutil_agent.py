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

"""Implements an Agent that uses gsutil to interact with Google Cloud Storage.

Ideally this would be an HttpAgent using the GCS API, however I was having
trouble getting this to reliably install on a generic OS/X machine
without an existing python environment so am using gsutil for the time being.
gsutil isnt ideal here because it has a more limited API and doesnt provide
as complete information. But it is good enough for basic testing.
"""


# Standard python modules.
import json
import os

# Our modules.
from ..service_testing import cli_agent
from ..base import JournalLogger
from ..base.json_scrubber import JsonScrubber


# This uses gsutil command line because I had trouble getting the python
# library to install on OS/X and dont want to get hung up on that for now.
# We'll return simple json as if we were using the HTTP interface. gsutil
# doesnt provide as usable an interface.
class GsutilAgent(cli_agent.CliAgent):
  """Agent that uses gsutil program to interact with Google Cloud Storage.
  """
  def __init__(self):
    """Construct instance."""
    super(GsutilAgent, self).__init__('gsutil', output_scrubber=JsonScrubber())

  def list(self, bucket, path, with_versions=False):
    """List the contents of the path in the specified bucket.

    Args:
      bucket: [string] The name of the bucket to list.
      path: [string] The path within the bucket to list.
         If path is a directory, it will list the immediate contents, but
         not content of any subdirectories.
      with_versions: [boolean] Whether or not to list all the versions.
         If path is a directory, this will list all the versions of all the
         files. Otherwise just all the versions of the given file.
    """
    args = ['ls']
    if with_versions:
      args.append('-a')
    args.append('gs://' + os.path.join(bucket, path))
    result = self.run(args)
    if not result.ok:
      return result

    found = []
    for item in result.output.split('\n'):
      marker = item.find('#')
      if marker < 0:
        info = {'name': item}
      else:
        info = {'name': item[0:marker], 'generation': item[marker + 1:]}
      found.append(info)

    output = json.JSONEncoder().encode(found)
    JournalLogger.journal_or_log(
        'Transforming output into json\n{0}'.format(output))

    return cli_agent.CliResponseType(result.exit_code, output, '')

  def retrieve(self, bucket, path):
    """Retrieves the content at the specified path.

    Args:
      bucket: [string] The bucket to retrieve front.
      path: [string] The path to the content to retrieve from the bucket.
    """
    return self.run(['cat', 'gs://' + os.path.join(bucket, path)])
