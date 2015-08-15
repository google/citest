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


"""Helper functions for managing configuration using parser.ArgumentParser."""


import re


def parser_args_to_bindings(args_namespace):
  """Create a bindings name/value dictionary from a parser argument namespace.

  Args:
    args_namespace: An argparse.Namespace returned from parsing
        command-line arguments.

  Returns:
    Dictionary of string values keyed by upper case names.
  """
  bindings = {}

  for key,value in vars(args_namespace).items():
    bindings[key.upper()] = value
  return bindings


def merge_args_namespace_and_config_dict(args_namespace, config_dict):
  """Create a name/value dictionary from an argparse Namespace.

  Args:
    args_namespace: A Namespace returned from parsing command-line arguments.
    config_dict: A name/value pair dictionary to merge into.
       The keys in the config_dict are in upper case.

  Returns:
    A copy of config_dict with the args_namespace values added into it.
    Duplicate values will take precedence from the args_namespace.
  """
  merge = config_dict.copy()        # Lower priority.
  merge.update(parser_args_to_bindings(args_namespace))
  return merge


def replace(text, bindings):
  """Replace the variables in text with their corresponding bindings.

  Args:
    text: The text to replace has variables in the form $<KEY>
    bindings: A dictionary of binding values keyed by <KEY>.
  """
  regex = re.compile(r'\$(\w+)')
  return regex.sub(lambda match: bindings.get(match.group(1), match.group()),
                   text)
