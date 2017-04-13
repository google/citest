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


"""Citest support modules for testing against Amazon Web Services (AWS)."""

from aws_cli_agent import AwsCliAgent
from aws_cli_contract import AwsCliContractBuilder

from aws_python_agent import AwsPythonAgent
from aws_python_contract import AwsPythonContractBuilder
from aws_python_contract import AwsErrorVerifier

# Deprecated Aliases
from aws_cli_agent import AwsCliAgent as AwsAgent
from aws_cli_contract import AwsCliContractBuilder as AwsContractBuilder
