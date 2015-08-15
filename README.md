# Summary
Cloud Integration Testing Framework (citest) is a python package to facilitate
writing integration tests against the REST style APIs typically used by
cloud services.

The gist is to allow tests to be written using a literary programming style
where the core framework accomodates for asynchronous calls and even retries
if appropriate.


# Example
A test case might look something like this:

```
  def create_network_load_balancer(self):
    load_balancer_name = self._bindings['TEST_APP_COMPONENT_NAME']
    target_pool_name = '{0}/targetPools/{1}-tp'.format(
      self._bindings['TEST_REGION'], load_balancer_name)

    payload = self.substitute_variables(
      '{"job":'
      '[{'
        '"provider":"gce",'
        '"stack":"$TEST_STACK",'
        '"detail":"$TEST_COMPONENT_DETAIL",'
        '"credentials":"$TEST_ACCOUNT_NAME",'
        '"region":"$TEST_REGION",'
        '"healthCheckPort":80,'
        '"healthTimeout":1,"healthInterval":1,'
        '"healthyThreshold":1,"unhealthyThreshold":1,'
        '"listeners":[{"protocol":"TCP","portRange":"80","healthCheck":true}],'
        '"name":"' + load_balancer_name + '",'
        '"providerType":"gce",'
        '"healthCheck":"HTTP:80/",'
        '"type":"upsertAmazonLoadBalancer",'
        '"availabilityZones":{"$TEST_REGION":[]},'
        '"user":"[anonymous]"'
      '}],'
      '"application":"$TEST_APP_NAME",'
      '"description":"Create Load Balancer: ' + load_balancer_name + '"}'
    )

    contract = GceContract(self._gcloud)
    (contract.new_clause('Health Check Added')
       .list_resources('http-health-checks')
       .contains('name', '%s-hc' % load_balancer_name))
    (contract.new_clause('Target Pool Added')
       .list_resources('target-pools')
       .contains('name', '%s-tp' % load_balancer_name))
    (contract.new_clause('Forwarding Rules Added', retryable_for_secs=30)
       .list_resources('forwarding-rules')
       .contains_group([PathContains('name', load_balancer_name),
                        PathContains('target', target_pool_name)]))

    test_case = OperationTestCase(
      self.newPostOperation(
        title='create_network_load_balancer', data=payload,
        path='applications/%s/tasks' % self.TEST_APP_NAME),
      contract=contract)
```


Where the test can be executed like this:

```
  self.run_test_case(test_case)
```


# Overview

## Abstract Model

Integration tests are written against services by sending an operation to
the service then observing the effects of that operation and verifying them
against expectations.

`citest` introduces a `TestableAgent` class for adapting external services
to the framework where the agent is responsible for understanding the
transport and protocol for exchanging messages with the service. It introduces
some basic concrete types such as `HttpAgent` and `CliAgent` where the primary
means is HTTP messaging or running a command-line program. Specific systems
may need to further specialize these to understand any additional application
protocols added, such as status responses for asynchronous HTTP messaging.

`TestableAgent` also acts as an `AgentOperation` factory where the operations
provide a means to wrap these serivce calls as first-class objects understood
by the core `clitest` framework. This allows `clitest` to invoke (or reinvoke)
the operation when it is appropriate to do so, rather than when the static code
is specifying what the test will be. When executed, the `AgentOperation` will
create an `OperationStatus` allowing `clitest` to track its progress and
eventual result.

In order to verify the operation, `clitest` uses `Contract` objects. A contract
is a collection of `ContractClause` where each clause can look for different
effects. A `ContractClause` is typically composed of an observation on the
effects and an assertion about what is expected to be observed. The observation
is made by an `Observer` that collects data in an `Observation` by working with
a `TestableAgent` to collect the data (e.g. an HTTP GET on some
JSON resource). The assertion is made by looking for expected values and
patterns in the collected resources. Each clause can collect different
resources.

The assertions are written using specialized `ValuePredicate` objects, which
are python callable classes that take the object value to be validate and return
a `PredicateResult` containing the conclusion and justification for it.

When a test is run, it will provide a trace of the operations performed,
data collected and justifications as to why it thinks the collected data
meets or does not meet expectations, ultimately passing or failing the test.



## Physical Organization

SubPackage | Purpose
-------|--------
base | Introduces some classes and utilities that support other packages.
json_contract | Introduces a means to specify contracts on JSON documents as a building block for testing.
service_testing | Introduces the core framework, base classes, and generic utilities.
aws_testing | Specializations and extensions to support testing on Amazon Web Services (AWS)
gcp_testing | Specializations and extensions to support testing on Google Cloud Platform (GCP)
tests | Tests for this package


# Contributing

See the CONTRIBUTING file for more information.


# License

See the LICENSE file for more information.

The package is composed of several subpackages of indivual modules.


# Contact Info

For more information, problems, or interest, contact ewiseblatt@google.com.

