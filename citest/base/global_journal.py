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


"""Implements a globally available journal."""

import atexit
import os
import stat
import threading

from . import Journal

# pylint: disable=invalid-name
# pylint: disable=global-statement
_added_atexit = False
_global_lock = threading.Lock()
_global_journal = None


def _atexit_handler():
  """Exit handling will finish the global journal so that it is well formed."""
  global _global_journal
  _global_lock.acquire(True)
  try:
    if _global_journal is not None:
      _global_journal.terminate()
      _global_journal = None
  finally:
    _global_lock.release()


def new_global_journal_with_path(path, **metadata):
  """Creates a global journal persisted at the provided path.

  Args:
    path: [string] The path to the journal to open.
    metadata: [kwargs] The journal metadata to write into the journal.
  """
  global _global_journal
  global _added_atexit
  _global_lock.acquire(True)
  try:
    if _global_journal is not None:
      raise ValueError('Global journal was already set.')

    if not _added_atexit:
      atexit.register(_atexit_handler)
      _added_atexit = True

    journal_file = open(path, 'wb')
    # Protect sensitive data.
    if hasattr(os, "fchmod"):
      os.fchmod(journal_file.fileno(), stat.S_IRUSR | stat.S_IWUSR)
    journal = Journal()
    journal.open_with_file(journal_file, **metadata)

    _global_journal = journal
  finally:
    _global_lock.release()

  return journal


def set_global_journal(journal):
  """Sets the global journal to the provided journal.

  Args:
    journal: [Journal] The journal
  """
  global _global_journal
  global _added_atexit
  if journal is None:
    raise ValueError('Journal not provided.')

  _global_lock.acquire(True)
  try:
    if _global_journal is not None:
      raise ValueError('Global journal was already set.')

    if not _added_atexit:
      atexit.register(_atexit_handler)
      _added_atexit = True

    _global_journal = journal
  finally:
    _global_lock.release()


def get_global_journal():
  """Returns the global journal."""
  # pylint: disable=global-variable-not-assigned
  global _global_journal
  _global_lock.acquire(True)
  result = _global_journal
  _global_lock.release()
  return result


def unset_global_journal():
  """Unsets the global journal, if it was already set.

  Returns:
    The previously global journal (if any) is not terminated.
  """
  global _global_journal
  _global_lock.acquire(True)
  result = _global_journal
  _global_journal = None
  _global_lock.release()
  return result
