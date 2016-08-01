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
from .gcp_agent import GcpAgent


STORAGE_READ_ONLY_SCOPE = 'https://www.googleapis.com/auth/devstorage.read_only'
STORAGE_READ_WRITE_SCOPE = 'https://www.googleapis.com/auth/devstorage.read_write'
STORAGE_FULL_SCOPE = 'https://www.googleapis.com/auth/devstorage.full_control'


class GcpStorageAgent(GcpAgent):
  """Agent that interacts with Google Cloud Storage service."""

  @classmethod
  def scope_aliases(cls):
    """Implements GcpAgent interface."""
    return {
        'read-only': STORAGE_READ_ONLY_SCOPE,
        'read-write': STORAGE_READ_WRITE_SCOPE,
        'full': STORAGE_FULL_SCOPE
    }

  @classmethod
  def default_discovery_name_and_version(cls):
    return 'storage', 'v1'

  def inspect_bucket(self, context, bucket, path=None, **kwargs):
    """Get metadata for a bucket or object in the bucket.

    Args:
      bucket: [string] The bucket to inspect.
      path: [string] The name of the object in the bucket.
         If None then inspect the bucket itself.

    Returns:
      Metadata for specified resource.
    """
    path = context.eval(path)
    if not path:
      return self.get_resource(context, 'buckets', bucket=bucket, **kwargs)
    else:
      return self.get_resource(context, 'objects', bucket=bucket, object=path,
                               **kwargs)

  def list_bucket(self, context, bucket, path_prefix, with_versions, **kwargs):
    """List the contents of the path in the specified bucket.

    Args:
      bucket: [string] The name of the bucket to list.
      path_prefix: [string] The path prefix of objects within the bucket
         to list.
      with_versions: [boolean] Whether or not to list all the versions.
         If path is a directory, this will list all the versions of all the
         files. Otherwise just all the versions of the given file.

    Returns:
      A list of resources.
    """
    return super(GcpStorageAgent, self).list_resource(
        context, 'objects', bucket=bucket, prefix=path_prefix,
        versions=with_versions, **kwargs)

  def retrieve_content(
      self, context, bucket, path, transform=None, generation=None, **kwargs):
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
    bucket = context.eval(bucket)
    path = context.eval(path)
    generation = context.eval(generation)
    request = self.service.objects().get_media(
        bucket=bucket,
        object=path,
        generation=generation,
        **kwargs)

    data = io.BytesIO()
    downloader = MediaIoBaseDownload(data, request, chunksize=1024*1024)
    done = False
    while not done:
      status, done = downloader.next_chunk()
      if status:
        self.logger.debug('Download %d%%', int(status.progress() * 100))
    result = data.getvalue()
    return result if transform is None else transform(result)
