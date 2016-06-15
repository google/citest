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

"""Implements an Agent that interacts with Google Cloud Storage."""

import io

from apiclient.http import MediaIoBaseDownload
from .gcp_api import build_authenticated_service
from ..service_testing import base_agent


READ_ONLY_SCOPE = 'https://www.googleapis.com/auth/devstorage.read_only'
READ_WRITE_SCOPE = 'https://www.googleapis.com/auth/devstorage.read_write'
FULL_SCOPE = 'https://www.googleapis.com/auth/devstorage.full_control'


class GoogleCloudStorageAgent(base_agent.BaseAgent):
  """Agent that interacts with Google Cloud Storage service."""

  def __init__(self, json_credential_path, scope):
    """Constructs agent.

    Args:
      json_credential_path: [string] path to JSON credentials for
          service account.
      scope: [string] The OAuth scope specifier for the agent when requesting
          credentials
    """
    super(GoogleCloudStorageAgent, self).__init__()
    self.__service = build_authenticated_service(
        'storage', 'v1', scope, json_credential_path)

  def inspect(self, bucket, path=None, generation=None):
    """Get metadata for a bucket or object in the bucket.

    Args:
      bucket: [string] The bucket to inspect.
      path: [string] The name of the object in the bucket.
         If None then inspect the bucket itself.
      generation: [long] The Google Cloud Storage generation, or None for
         the current generation.

    Returns:
      Metadata for specified resource.
    """
    if not path:
      self.logger.info('Inspecting bucket=%s', bucket)
      request = self.__service.buckets().get(bucket=bucket)
    else:
      maybe_gen = ' generation={0}'.format(generation) if generation else ''
      self.logger.info('Inspecting bucket=%s, path=%s%s',
                       bucket, path, maybe_gen)
      request = self.__service.objects().get(bucket=bucket, object=path,
                                             generation=generation)
    response = request.execute()
    self.logger.info('%s', response)
    return response

  def list(self, bucket, path_prefix, with_versions, maxResults=1000,
           fields=None):
    """List the contents of the path in the specified bucket.

    Args:
      bucket: [string] The name of the bucket to list.
      path_prefix: [string] The path prefix of objects within the bucket
         to list.
      with_versions: [boolean] Whether or not to list all the versions.
         If path is a directory, this will list all the versions of all the
         files. Otherwise just all the versions of the given file.
      maxResults: [int] Max results to get. This will be passed through to
         Google Cloud Storage (which defaults to 1000).
      fields: [string] A comma-delimited selector indicating the subset of
         fields to include as partial responses, or None for everything.

    Returns:
      A list of resources.
    """
    self.logger.info('Listing bucket=%s prefix=%s versions=%s',
                     bucket, path_prefix, with_versions)
    request = self.__service.objects().list(
        bucket=bucket, prefix=path_prefix, versions=with_versions,
        maxResults=maxResults, fields=fields)

    all_objects = []
    while request:
      response = request.execute()
      all_objects.extend(response.get('items', []))
      request = self.__service.objects().list_next(request, response)
    return all_objects

  def retrieve(self, bucket, path, generation=None, transform=None):
    """Retrieves the content at the specified path.

    Args:
      bucket: [string] The bucket to retrieve front.
      path: [string] The path to the content to retrieve from the bucket.
      generation: [long] Specifies version of object (or None for current).
      transform: [callable(string)] transform the downloaded bytes into
         something else (e.g. a JSON object). If None then the identity.

    Returns:
      transformed object.
    """
    self.logger.info('Retrieving path=%s from bucket=%s [generation=%s]',
                     path, bucket, generation)

    # Get Payload Data
    request = self.__service.objects().get_media(
        bucket=bucket,
        object=path,
        generation=generation)

    data = io.BytesIO()
    downloader = MediaIoBaseDownload(data, request, chunksize=1024*1024)
    done = False
    while not done:
      status, done = downloader.next_chunk()
      if status:
        self.logger.debug('Download %d%%', int(status.progress() * 100))
    result = data.getvalue()
    return result if transform is None else transform(result)
