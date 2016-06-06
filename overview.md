# Summary

Cloud Integration Testing Framework (citest) is a python package to facilitate
writing integration tests against the REST style APIs typically used by
cloud services. Citest can be used on its own, but it is designed to complement
other testing techniques (e.g. unit testing) and other test infrastructure
(e.g. provisioning test environments) as opposed to being a single comprehensive
testing solution. The focal points of citest are:

* **Specifying test cases in a concise way** -- limited boilerplate code.

* **Performing independent verification** that systems are behaving as expected.

* **Reporting with traceability** to understand what has been tested, and
  facilitate debugging when tests fail.


Citest is designed for API level testing of live distributed asynchronous systems.
It is not designed for testing User Interfaces.


# Citest Overview

A citest module test is a collection of related tests against a live system.
The system is not necessarily running in production serving public traffic but,
but as far as the test client is concerned, it is testing in a "real" environment
as opposed to using fakes and mocks.

Each test performs an operation against the system and verifies that the
behavior is as expected. Typically this is by both checking the results
returned by the operation as well as independently observing side effects
to verify that the system is doing what it claims to do.

In addition to performing and verifying operations, citest reports all its
activities and interactions in order to provide additional insight and
traceability into exactly what is being tested and why it believes that tests
have passed (or failed). This is useful to debug the systems as well as to
understand how the system is being tested and exactly what the tests are.

In order to test a new system, your system, you will typically need to write
up to four types of code.


1. The actual tests to perform are typically straight forward and concise.
   A test is a `citest.service_testing.AgentOperation` and
   `citest.json_contract.Contract`. This pair is commonly specified together as a
   `citest.service_testing.OperationContract`.
   An *operation* typically specifies the call to make. For example, if you are
   testing an HTTP interface, the operation will be the URL and data payload
   *if a POST). The *contract* specifies one or more
   `citest.json_contract.ContractClause`, where a clause is an observation to make
   and different expectations of things to see. For example if we asked to
   create a resource, the contract would verify that the resource was created,
   and contains certain attributes that we expect based on what or how we created
   it. Different clauses may test different aspects of the resource where
   different types of observations may be required.

   Contracts are typically composed from `citest.json_predicate.ValuePredicate`
   objects whose API lets you concisely specify relationships of objects and
   values. For example, verify that a given attribute (possibly nested deep
   within other embedded components) contains certain attributes an values.
   

2. Depending on the interface to your system, you may need to write a
   `citest.service_testing.BaseAgent` adapter in order for the core citest
   components to interact with it (i.e. manage the operations in your tests,
   and collect the observations). The agent that performs operations could be
   different than the agent that observes your system. That is up to you and
   the needs of the test you are writing. Agents are written by specializing the
   `citest.service_testing.BaseAgent` interface (or derivitive).

3. Depending on what your operations look like, you may need to specialize the
   `citest.service_testing.AgentOperation` interface and/or the
   `citest.service_testing.AgentOperationStatus` interface. citest assumes that
   operations are asynchronous so uses an `AgentOperationStatus` interface to
   provide access to the current status and signal when an operation has finished.

4. Finally, some code that coordinates and runs the tests. This code is typically
   simple because the citest framework does most of the work given the operations
   and contracts. However, if module tests contain interdependent tests, then
   you may want to share some state across them, such as the names of resources
   that were created. Citest defines a Scenario class which is intended to
   capture the shared state for a collection of interrelated tests. In practice
   this is merely a call to `run_test_case` passing the `OperationContract` and
   letting the core framework take it from there.


# Example Case Study: Testing Spinnaker

[Spinnaker](http://spinnaker.io) is a multi-cloud continuous delivery platform.
Spinnaker uses citest to verify its core interactions with the different cloud
platforms actually works to complement its extensive internal unit tests that
verify the implementation and internal state is as intended. Spinnaker provides
REST style HTTP interfaces using JSON encoded objects. Therefore, operations make
use of the standard `citest.service_testing.HttpAgent` built into citest.
However, Spinnaker uses a custom application protocol where operations return the
URL that is polled for the operation status. That status URL returns a custom
data object that describes the current status and final operation state.
Furthermore, spinnaker is composed of multiple systems, some of which implement
different application protocols (the status objects look different). To capture
commonalities among the different systems while allowing for their specialization,
some additional classes were defined to extend the citest platform to add
Spinnaker specializations. These extensions are part of Spinnaker, not citest.
Currently they are located in the same repository as citest
(in `spinnaker.*` modules) though this is not a normal recommended practice and
the spinnaker/ branch will be moved to a different repository in the future.

Since Spinnaker operations are used to modify resources on cloud provider
platforms its citests use the native platform's SDK tools to inspect the platform
to see if Spinnaker modified the right resources as expected. For convienence,
it uses the command-line program that the platforms provide. citest has Agent
implementations for these so that they can be used by observers to collect
observation data based on cloud provider resources. The alternative would be to
use the native platform API rather than calling back into Spinnaker. At least in
this case, there is no reason to trust Spinnaker since we can perform independent
verification by obtaining ground truth from the platform itself.

## Example: Configuring the test

Tests will often contain some values that require configuration as opposed to
being static. For example, the network endpoint of the service being tested.
citest uses 'bindings' for these. Bindings is simply a dictionary of name/value
pairs. The binding dictionary uses upper case keys by convention. Custom names
can be added as commandline parameters so they can be controlled from the
command-line, then used to form the internal bindings used by tests. Not all
bindings need to be command-line arguments. This is left to the disgression of
the test author for convienence.


In this example, Spinnaker tests provide command-line arguments to specify the
location of the server. In general, this can be done with the 'native_hostname'
parameter (specifies the IP address or DNS hostname). However it also defines
a project/zone/instance that can be convienent to use on Google Cloud Platform.
citest does not directy support this choice so this will require extra
application code. However since services are typically firewalled for security
and require clients to tunnel into them, using the GCE project/zone/instance
parameters lets us use citest's GCP support that can establish the ssh tunnel
for us if it turns out that we cannot otherwise reach the server directly.
[NOTE: there is also a port binding, but it is not interesting to discuss here.]


```python
class SpinnakerTestScenario(sk.AgentTestScenario):
  @classmethod
  def initArgumentParser(cls, parser, defaults=None):
    parser.add_argument(
        '--native_hostname', default=defaults.get('NATIVE_HOSTNAME', None),
        help='Host name that {system} is running on.'
             ' This parameter is only used if the spinnaker host platform'
             ' is "native".'.format(system=subsystem_name))

    parser.add_argument(
        '--gce_project', default=defaults.get('GCE_PROJECT', None),
        help='The GCE project that {system} is running within.'
             ' This parameter is only used if the spinnaker host platform'
             ' is GCE.'.format(system=subsystem_name))
    parser.add_argument(
        '--gce_zone', default=defaults.get('GCE_ZONE', None),
        help='The GCE zone that {system} is running within.'
             ' This parameter is only used if the spinnaker host platform'
             ' is GCE.'.format(system=subsystem_name))
    parser.add_argument(
        '--gce_instance', default=defaults.get('GCE_INSTANCE', None),
        help='The GCE instance name that {system} is running on.'
             ' This parameter is only used if the spinnaker host platform'
             ' is GCE.'.format(system=subsystem_name))


def main():
  """Implements the main method running this smoke test."""

  defaults = {
      'TEST_STACK': str(GoogleSmokeTestScenario.DEFAULT_TEST_ID),
      'TEST_APP': 'gcpsmoketest' + GoogleSmokeTestScenario.DEFAULT_TEST_ID
  }

  return st.ScenarioTestRunner.main(
      GoogleSmokeTestScenario,
      default_binding_overrides=defaults,
      test_case_list=[GoogleSmokeTest])
```

The `main()` here defines some default binding values then calls the standard
`citest.service_testing.ScenarioTestRunner`. It passes in the test scenario
used by our tests, and the test class defining the test suite that we will run.
The scenario is used to initialize the argument parser and will be instantiated
and passed into the test case.


## Example: Creating an Agent (so citest can talk to Spinnaker)

Here, "gate" is a custom module we wrote to adapt Spinnaker's "gate" service.
It provides a factory function "new_agent" to create an instance of BaseAgent.
We'll show how this is implemented in a futue example. The point in this example
is that the `service_testing.TestScenario` class (of which SpinnakerTestScenrio is
derived) lets you add a classmethod called "new_agent" that acts as a factory
method. The base `citest.service_testing.TestScenario` will call this method at
some point to construct the agent it needs.


```python
import spinnaker_testing.gate as gate
class AwsSmokeTestScenario(sk.SpinnakerTestScenario):
  @classmethod
  def new_agent(cls, bindings):
    """Implements citest.service_testing.AgentTestScenario.new_agent."""
    return gate.new_agent(bindings)
```


## Example: A simple test specifying an operation and its contract.

The following example shows a test on Spinnaker's interface to create a server
group on Amazon Web Services. The particular parameters and bindings here,
including `self.TEST_APP`, are specific to Spinnaker. The gist is that we're
creating a payload with some data, some of which happens to be parameterized
by bindings.

```python
class AwsSmokeTestScenario(sk.SpinnakerTestScenario):
  def create_server_group(self):
    bindings = self.bindings

    # Spinnaker determines the group name created,
    # which will be the following:
    group_name = '{app}-{stack}-v000'.format(
        app=self.TEST_APP, stack=bindings['TEST_STACK'])

    payload = self.agent.make_json_payload_from_kwargs(
        job=[{
            'type': 'createServerGroup',
            'cloudProvider': 'aws',
            'application': self.TEST_APP,
            'stack': bindings['TEST_STACK'],
            'credentials': bindings['AWS_CREDENTIALS'],
            'capacity': {'min':2, 'max':2, 'desired':2},
            ...
        }],
        description='Create Server Group in ' + group_name,
        application=self.TEST_APP)

    builder = aws.AwsContractBuilder(self.aws_observer)
    (builder.new_clause_builder('Auto Server Group Added',
                                retryable_for_secs=30)
     .collect_resources('autoscaling', 'describe-auto-scaling-groups',
                        args=['--auto-scaling-group-names', group_name])
     .contains_path_value('AutoScalingGroups', {'MaxSize': 2}))

    return st.OperationContract(
        self.new_post_operation(
            title='create_server_group', data=payload, path='tasks'),
        contract=builder.build())
```   

There are three parts to this method.
   1. Define the payload that we'll send. It defines a bunch of attributes
      including a capacity that specifies a capacity size of 2.

   2. Define the contract we expect the operation to uphold. There is one clause,
      which expects that we created an autoscaling group of the right size.
      The `collect_resources()` method is specifying the observation to make.
      The AwsContractBuilder defines this particular method as the point of the
      builder is to make observations of AWS resources and verify them. This
      particular observer is a command-line agent and lets us specify special
      parameters we need to pass to observe.

      The `contains_path_value()` is a constraint we wish to verify on the
      observation. This method is shorthand notation for using a path predicate
      to extract an attribute ('AutoScalingGroups') from an observed object
      and verify that its value includes another value. In this case the value
      is a dictionary that includes an attribute named 'MaxSize' with value 2.

      Note also that the contract itself is retryable for 30 seconds. This means
      that it is ok if the contract is not met when the operation first completes,
      however should eventually become true within the next 30 seconds thereafter.
      This is because the asynchronous operation in our system completes once it
      tells AWS to create the group, however the group takes time to actually
      create and become available for us to properly observe and verify.

   3. We construct the actual test object. This is the Operation to perform
      (an HTTP POST of the payload we created to the server's 'tasks' URL),
      and the contract to verify. Note that we do not actually run the test here.
      Instead citest lets us define first class objects that specify the test to
      be performed, then will handle the scheduling and execution of these tests
      as it sees fit.


To execute the test, we use the standard python unittest classes. Although these
arent unit tests, the classes provide a convienent basis and standard hooks for
citest to leverage.

```python
class AwsSmokeTest(st.AgentTestCase):
  ...
  def test_c_create_server_group(self):
    self.run_test_case(self.scenario.create_server_group())
```

The heavy lifting here is performed by citest's
`citest.service_testing.AgentTestCase.run_test_case()` method, taking the server
group test object we created earlier. Note that we are currently using this
unittest class to explicitly schedule and run the test. However in the future,
a different mechanism based on the test objects may be introduced.


## Example: A simple test specifying an operation and its multi-clause contract.

The following test creates a Spinnaker load balancer on GCE. A spinnaker
load balancer consists of 3 different components, requiring us to make
multiple observations of different components in order to verify it is correct.

```python
import citest.json_predicate as jp

class GoogleSmokeTestScenario(sk.SpinnakerTestScenario):
  def __init__(self, bindings, agent=None):
    super(GoogleSmokeTestScenario, self).__init__(bindings, agent)
    bindings = self.bindings
    self.__lb_detail = 'lb'
    self.__lb_name = '{app}-{stack}-{detail}'.format(
        app=bindings['TEST_APP'], stack=bindings['TEST_STACK'],
        detail=self.__lb_detail)
    ...

  def upsert_load_balancer(self):
    bindings = self.bindings
    target_pool_name = '{0}/targetPools/{1}-tp'.format(
        bindings['TEST_GCE_REGION'], self.__lb_name)

    spec = {
        'checkIntervalSec': 9,
        'healthyThreshold': 3,
        'unhealthyThreshold': 5,
        'timeoutSec': 2,
        'port': 80
    }

    payload = self.agent.make_json_payload_from_kwargs(
        job=[{
            'cloudProvider': 'gce',
            'provider': 'gce',
            'stack': bindings['TEST_STACK'],
            'detail': self.__lb_detail,
            'credentials': bindings['GCE_CREDENTIALS'],
            'region': bindings['TEST_GCE_REGION'],
            'ipProtocol': 'TCP',
            'portRange': spec['port'],
            'loadBalancerName': self.__lb_name,
            'healthCheck': {
                'port': spec['port'],
                'timeoutSec': spec['timeoutSec'],
                'checkIntervalSec': spec['checkIntervalSec'],
                'healthyThreshold': spec['healthyThreshold'],
                'unhealthyThreshold': spec['unhealthyThreshold'],
            },
            'type': 'upsertLoadBalancer',
            'availabilityZones': {bindings['TEST_GCE_REGION']: []},
            'user': '[anonymous]'
        }],
        description='Create Load Balancer: ' + self.__lb_name,
        application=self.TEST_APP)

    builder = gcp.GceContractBuilder(self.gce_observer)
    (builder.new_clause_builder('Health Check Added',
                                retryable_for_secs=30)
     .list_resources('http-health-checks')
     .contains_pred_list(
         [jp.PathContainsPredicate('name', '%s-hc' % self.__lb_name),
          jp.DICT_SUBSET(spec)]))
    (builder.new_clause_builder('Target Pool Added',
                                retryable_for_secs=30)
     .list_resources('target-pools')
     .contains_path_value('name', '%s-tp' % self.__lb_name))
    (builder.new_clause_builder('Forwarding Rules Added',
                                retryable_for_secs=30)
     .list_resources('forwarding-rules')
     .contains_pred_list([
          jp.PathContainsPredicate('name', self.__lb_name),
          jp.PathContainsPredicate('target', target_pool_name)]))

    return st.OperationContract(
        self.new_post_operation(
            title='upsert_load_balancer', data=payload, path='tasks'),
        contract=builder.build())
```

This is similar to the AWS server group example above. Here the contract
consists of three clauses. The first verifies that we created a health check
with an expected name and configured the health check in a particular way
by comparing it's JSON object to the specification we expect it to have (and
used to form the request). The "list_resources" method is added by the
`GceContractBuilder` -- in this case to collect all the GCP http-health-checks.
Due to the nature of Spinnaker's implementation, we do not know the exact name
that it used to ensure uniqueness. However we know part of the substring that
the name should have (and have ourselves chosen it to be unique).

The other clauses are simlilar but happen to use different types of predicates.
The `contains_pred_list()` is checking that each of the predicates holds on a
particular object. This would be the same as the `jp.DICT_SUBSET` predicate,
however reporting is different should one of these predicates fail, the individual
attributes will be shown as opposed to the entire dict since these are independent
predicates.


## Example: A custom OperationStatus implementation

The following is an excerpt from SpinnakerStatus specialization to adapt
citest to Spinnaker's application protocol. The spinnaker HTTP operations
return a URL that, when queried, returns a JSON object describing the status.
The following class is an implementation of the citest object that interprets
the operation result payload (the URL to poll) and the JSON status details.

This particular class is still abstract because different spinnaker services
define different JSON object schemas. Only parts of the class are shown here.
For the complete details, see: https://raw.githubusercontent.com/google/citest/master/spinnaker/spinnaker_testing/spinnaker.py

The gist of what is happening here is that the abstract class defines its
interface in terms of properties. The `citest.service_testing.HttpOperationStatus`
adds in interface `set_http_response` that asks the instance to update its
state based on the HTTP response it retrieved. We implement this by parsing the
JSON data we expect in the response, and pulling out the attributes we need to
satisfy the interface needs. The actual method to parse the JSON is left to the
specialized class for each of the different subsystems since this varies.

```python
class SpinnakerStatus(service_testing.HttpOperationStatus):
  @property
  def current_state(self):
    """The value of the JSON "state" field, or None if not known."""
    return self.__current_state

  @current_state.setter
  def current_state(self, state):
    """Updates the current state."""
    self.__current_state = state

  def error(self):
    return self.__error

  @property
  def exception_details(self):
    return self.__exception_details

  @property
  def id(self):
    return self.__request_id

  @property
  def detail_path(self):
    return self.__detail_path

  def export_to_json_snapshot(self, snapshot, entity):
    super(SpinnakerStatus, self).export_to_json_snapshot(snapshot, entity)
    snapshot.edge_builder.make_output(entity, 'Status Detail', self.__json_doc,
                                      format='json')

  def __init__(self, operation, original_response=None):
    super(SpinnakerStatus, self).__init__(operation, original_response)
    self.__request_id = original_response.output
    self.__current_state = None  # Last known state (after last refresh()).
    self.__detail_path = None    # The URL path on spinnaker for this status.
    self.__exception_details = None
    self.__error = None
    self.__json_doc = None

    if not original_response or original_response.http_code is None:
      self.__current_state = 'REQUEST_FAILED'
      return

  def refresh(self, trace=True):
    if self.finished:
      return

    http_response = self.agent.get(self.detail_path, trace=trace)
    try:
      self.set_http_response(http_response)
    except BaseException as bex:
      raise

  def set_http_response(self, http_response):
    if http_response.http_code is None:
      self.__current_state = 'Unknown'
      return

    decoder = JSONDecoder()
    self.__json_doc = decoder.decode(http_response.output)
    self._update_response_from_json(self.__json_doc)

  def _update_response_from_json(self, doc):
    # pylint: disable=unused-argument
    raise Exception("_update_response_from_json is not specialized.")


class GateTaskStatus(sk.SpinnakerStatus):
  @classmethod
  def new(cls, operation, original_response):
    return GateTaskStatus(operation, original_response)

  @property
  def timed_out(self):
    return (self.current_state == 'TERMINAL'
            and str(self.detail).find(' timed out.') > 0)

  @property
  def finished(self):
    return not self.current_state in ["NOT_STARTED", "RUNNING", None]

  @property
  def finished_ok(self):
    return self.current_state == 'SUCCEEDED'

  def __init__(self, operation, original_response=None):
    super(GateTaskStatus, self).__init__(operation, original_response)

    if not original_response.ok():
      self._bind_error(original_response.error_message)
      self.current_state = 'HTTP_ERROR'
      return

    doc = None
    try:
      doc = json.JSONDecoder().decode(original_response.output)
    except (ValueError, TypeError):
      pass

    if isinstance(doc, dict):
      self._bind_detail_path(doc['ref'])
      self._bind_id(self.detail_path)
    else:
      self._bind_error("Invalid response='{0}'".format(original_response))
      self.current_state = 'CITEST_INTERNAL_ERROR'

  def _update_response_from_json(self, doc):
    self.current_state = doc['status']
    self._bind_exception_details(None)

    exception_details = None
    gate_exception = None
    variables = doc['variables']
    if variables:
      for elem in variables:
        if elem['key'] == 'exception':
          value = elem['value']
          exception_details = value['details']
        elif elem['key'] == 'kato.tasks':
          value = elem['value']
          for task in value:
            if 'exception' in task:
              gate_exception = task['exception']['message']
              break

    self._bind_exception_details(exception_details or gate_exception)
```

# Appendix
## Running the Spinnaker Tests

The Spinnaker tests in the repository can serve as examples for citest tests.

To run them, you need to have Spinnaker deployed. See http://spinnaker.io for
how to do this. A starting point is [Target Deployment Setup]
(https://spinnaker.readme.io/docs/target-deployment-setup). Citest does not care
which method you use to deploy or where you deploy. However, different tests are
testing different providers. You'll need an account with a provider to
successfully run a test, but you can run tests without a provider and still
see them fail as long as you can talk to a Spinnaker server.

With the exception of the `bake_and_deploy_test`, which requires special
configuration of a Jenkins server (described in the test), the tests can all
be run the same way. A minimum google test looks like this:
```
  PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/<test> \
     --native_hostname=<host> \
     --gce_service_account=<account>
```

A minimum aws test looks like this:
```
  PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/<test> \
     --native_hostname=<host> \
     --aws_profile=<account>
```

The `--gce_service_service_account` and `--aws_profile` parameters configure
the observer with the credentials that it needs.  They require that you have
added the GCE service account to gcloud using gcloud auth activate-service-account
or added the AWS credentials for the aws command-line tool to a profile in
~/.aws/credentials. Note that both these flags are always valid in all the
spinnaker tests. Also, the credentials parameters can be ommitted if the tools
are configured with defaults that use the desired accounts already.

If Spinnaker is deployed on GCE then the recommended practice is to tunnel into it
because the recommended practice for spinnaker deployments is to not expose any
of the services outside the project for security reasons. If you are not running
the tests within the same project, then you can use the following parameters
instead of `--native_hostname` and Spinnaker will use citest to tunnel into the
server automatically as needed to run the tests. This is particularly convienent
since you dont have to worry about what ports to forward and citest will map
unused local ports so that you can run multiple tests concurrently without them
conflicting, and be assured that you are talking to the exact server you intended,
and not some other server that you were accidentally tunneled into.
   `--gce_project=<projectName> --gce_zone=<zone> --gce_instance=<instanceName>`
If you are not running [ssh-agent](https://en.wikipedia.org/wiki/Ssh-agent) with
your ssh passphrase added, you can create a file containing the passphrase and
add it to the test commandline and citest will use it as needed. Be sure to
`chmod 400` to protect this file.


```
PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/google_server_group_test.py \
  --gce_project=$GCP_PROJECT --gce_zone=$GCE_ZONE --gce_instance=$GCP_INSTANCE \
  --gce_ssh_passphrase_file=$HOME/.ssh/google_compute_engine.passphrase \
  --gce_service_account=$GCP_SERVICE_ACCOUNT

PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/google_smoke_test.py \
  --gce_project=$GCP_PROJECT --gce_zone=$GCE_ZONE --gce_instance=$GCP_INSTANCE \
  --gce_ssh_passphrase_file=$HOME/.ssh/google_compute_engine.passphrase
  --gce_service_account=$GCP_SERVICE_ACCOUNT

PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/google_kato_test.py \
  --gce_project=$GCP_PROJECT --gce_zone=$GCE_ZONE --gce_instance=$GCP_INSTANCE \
  --gce_ssh_passphrase_file=$HOME/.ssh/google_compute_engine.passphrase
  --gce_service_account=$GCP_SERVICE_ACCOUNT

PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/aws_kato_test.py \
  --gce_project=$GCP_PROJECT --gce_zone=$GCE_ZONE --gce_instance=$GCP_INSTANCE \
  --gce_ssh_passphrase_file=$HOME/.ssh/google_compute_engine.passphrase \
  --gce_service_account=$GCP_SERVICE_ACCOUNT
  --aws_profile=$AWS_PROFILE

PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/aws_smoke_test.py \
  --gce_project=$GCP_PROJECT --gce_zone=$GCE_ZONE --gce_instance=$GCP_INSTANCE \
  --gce_ssh_passphrase_file=$HOME/.ssh/google_compute_engine.passphrase \
  --gce_service_account=$GCP_SERVICE_ACCOUNT
  --aws_profile=$AWS_PROFILE

# See test for how to configure Jenkins for this test,
# and also be sure that spinnaker is configured for your Jenkins server.
PYTHONPATH=.:spinnaker \
  python spinnaker/spinnaker_system/bake_and_deploy_test.py \
  --test_google --test_aws \
  --jenkins_token=TRIGGER_TOKEN --jenkins_job=TestTriggerProject \
  --jenkins_url=$JENKINS_URL --jenkins_master=Jenkins \
  --gce_project=$GCP_PROJECT --gce_zone=$GCE_ZONE --gce_instance=$GCP_INSTANCE \
  --gce_ssh_passphrase_file=$HOME/.ssh/google_compute_engine.passphrase \
  --gce_service_account=$GCP_SERVICE_ACCOUNT
  --aws_profile=$AWS_PROFILE
```

