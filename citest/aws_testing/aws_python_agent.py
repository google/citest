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


"""Adapts citest BaseAgent to interact with Amazon Web Services.

See https://boto3.readthedocs.io/en/latest/reference/services/index.html
for underlying API.
"""


# Standard python modules.
import datetime
import json
import logging

import boto3

# Our modules.
from ..base import JournalLogger
from ..service_testing import BaseAgent


# This is here for now because it isnt that useful yet in general.
# Eventually move this to service_test/python_agent.

class PythonAgent(BaseAgent):
  """An agent that is built using python libraries."""

  def __init__(self):
    super(PythonAgent, self).__init__()
    self.logger = logging.getLogger(self.__class__.__module__)

  def _log_call_method_response(self, method, response):
    JournalLogger.journal_or_log(
        json.JSONEncoder(
            encoding='utf-8', separators=(',', ': ')).encode(response),
        _module=self.logger.name, _context='response',
        format='json')

  def call_method(self, method, context, *pos_args, **kwargs):
    """Invokes method and returns result.

    This is a wrapper around calling the method that will log the
    call and result.

    Args:
      method: callable method to invoke with *pos_args and **kwargs.
      context: [ExecutionContext]
      pos_args: [list]  positional arguments to pass to method.
      kwargs: [kwargs]to pass to method.
      _citest_log
    Raises:
      Exceptions thrown by method
    Returns:
      result of method
    """
    if hasattr(method, 'im_class'):
      method_name = '{0}.{1}'.format(method.im_class.__name__,
                                     method.im_func.__name__)
    else:
      method_name = str(method)

    eval_pos_args = context.eval(pos_args)
    eval_kwargs = context.eval(kwargs)
    JournalLogger.begin_context('Call {0}'.format(method_name))

    try:
      arg_text_list = [repr(arg) for arg in eval_pos_args]
      arg_text_list.extend(['{0}={1!r}'.format(key, value)
                            for key, value in eval_kwargs.items()])
      arg_text = ','.join(arg_text_list)

      JournalLogger.journal_or_log(
          '{0}({1})'.format(method_name, arg_text),
          _module=self.logger.name,
          _context='request')
      response = method(*eval_pos_args, **eval_kwargs)
      self._log_call_method_response(method, response)
      return response
    finally:
      JournalLogger.end_context()


class AwsJsonEncoder(json.JSONEncoder):
  def default(self, obj):
    if isinstance(obj, datetime.datetime):
      return obj.isoformat()
    return json.JSONEncoder.default(self, obj)



class AwsPythonAgent(PythonAgent):
  """A service_testing.PythonAgent that uses the aws tool to interact with AWS.

  Attributes:
    region: The default AWS region name to use for commands requiring one.
  """

  @classmethod
  def make_agent(cls, profile_name, **kwargs):
    """Factory method to create a new agent instance.

    Args:
      profile_name: [string] Indicate the credentials to use in .aws/credentials
    """
    return cls(profile_name, *kwargs)

  def  __init__(self, profile_name):
    """Construct instance."""
    super(AwsPythonAgent, self).__init__()
    self.__profile_name = profile_name

  def make_boto_client(self, module):
    if self.__profile_name:
      factory = boto3.Session(profile_name=self.__profile_name)
    else:
      factory = boto3

    try:
      return factory.client(module)
    except:
      raise ValueError('Unknown module {module}'.format(module=module))

  def export_to_json_snapshot(self, snapshot, entity):
    """Implements JsonSnapshotableEntity interface."""
    builder = snapshot.edge_builder
    builder.make_control(entity, 'Profile', self.__profile_name)
    super(AwsPythonAgent, self).export_to_json_snapshot(snapshot, entity)

  def _log_call_method_response(self, method, response):
    JournalLogger.journal_or_log(
        AwsJsonEncoder(
            encoding='utf-8', separators=(',', ':')).encode(response),
        _module=self.logger.name, _context='response',
        format='json')

  def call_method(self, context, _method, *pos_args, **kwargs):
    _response_field = kwargs.get('_response_field', None)
    response = super(AwsPythonAgent, self).call_method(
        _method, context, *pos_args, **kwargs)
    return response if _response_field is None else response[_response_field]

  def call_method_and_extract_singular_response(
      self, context, _method, _response_field, *pos_args, **kwargs):
    _exactly_one = kwargs.get('_exactly_one', True)
    if '_exactly_one' in kwargs:
      del kwargs['_exactly_one']

    kwargs['_response_field'] = _response_field
    response = call_method(_method, context, *pos_args, **kwargs)
    if _exactly_one and len(response) != 1:
      raise ValueError('Unexpected exactly response.')
    elif len(response) > 1:
      raise ValueError('Expected one result, not {0}'.format(len(response)))

    return response[0] if response else None
