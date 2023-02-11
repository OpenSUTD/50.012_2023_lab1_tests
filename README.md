# 50.012 Networks Lab 1 Test Suite

This project implements an automated test suite for the HTTP proxy lab. It spins up a few test web servers in a docker network and a test monitor that starts new instances of your proxies on demand. Finally there is a run-once docker container containing a pytest suite that that communicates with the monitor to test your proxy. All these docker containers are orchestrated as a single docker-compose project.

## Usage

### Installing your proxy code

Place your proxy Python files inside `proxy/app` (create the folder if it doesn't exist). You can have as many files as you like inside, but there MUST be a `proxy.py` file that starts the proxy on port 8080 when you start it.

### Starting the environment

```
docker-compose up -d
```

Deploying the compose project automatically starts the full basic test suite (no smoke tests). Wait for the `test-client` service to exit. In another terminal window you can watch the stdout of the test-client using:

```
docker-compose logs test-client -f
```

### Viewing results

#### Overall test results

The overral test results indicating test successes and failures will be saved in the file `test-client/result/result.log`. Only the latest invocation's results will be saved.

#### stdout/stderr for each test

A fresh instance of your proxy is started for each test that is run. You can go to `proxy/logs/{test-name}.log` to see what was printed to stdout and stderr by your proxy during each test. Only the latest invocation results will be saved.

#### Latest cache results

The cache directory will be left in the state of the last test run as it is cleaned at the start of each test. If debugging errors it is suggested you run one test at a time using the `-k` argument in `PYTEST_ADDOPTS`.

> If you open a log file in the editor and re-run the test suite, you need to reload the file from disk to get the latest version.

### Running the tests again

You can edit the files in the `proxy/app` folder directly if you are working to pass the tests. When you are ready to re-run the tests, restart the `test-client` container:

```
docker-compose start test-client
```

#### Running a different suite

By default, the test client only runs the `basic_test` suite. To run the extended smoke tests, edit the docker-compose.yml file and swap the commented lines under `services.test-client-environment`:

```yaml

# Run basic tests only
- PYTEST_TESTS=basic_test.py
# Run smoke tests only
# - PYTEST_TESTS=smoke_test.py
```

Changes to the compose file require you to update the deployment, just run `docker-compose up -d` again

#### Different test arguments, speeding up the test

The full test suite that will be using for grading tests every single static file in the `nginx/html` directory. When doing iterative testing this can get quite cumbersome. In the `docker-compose.yml` file, you can pass the add the pytest opt to control how many samples you want to test:

```yaml
      - PYTEST_ADDOPTS=-ra --tb=short --proxytest-nginx-static-files-n-samples=3
```

As above, changes to the compose file require you to update the deployment, just run `docker-compose up -d` again

#### Running a single test

Use the `-k` argument in `PYTEST_ADDOPTS`. See pytest documentation on [run tests by keyword expressions](https://docs.pytest.org/en/7.1.x/how-to/usage.html#specifying-which-tests-to-run).

### Troubleshooting & Debugging

#### test client hangs without errors

If after waiting for more than 60 seconds (the timeout configured in the HTTP clients) the test client docker container does not respond, stop the `test-client` conntainer and the `proxy` container. Then restart the `proxy` container, wait for it to be ready, then start the `test-client` container again.

#### Wireshark

A wireshark instance served over RDP is available in your web browser at `http://localhost:3000`. It runs on the proxy instance. So for example, you can capture all downstream HTTP-in-TCP datagrams using the packet filter `tcp port 8080`.

If the application stops responding, restart the `proxy-wireshark` container.

## Test Technicals

### Static Website tests

The `nginx-server` container serves static files from the `nginx-server/html` directory. You can add your own files to test here. The parametrized test `basic_test::test_request_nginx_body_unchanged` samples a list of static files in the html directory and tries to fetch the resources.

### Smoke Tests

The `smoke_test` suite is an extended suite for extreme edge cases. You will not be graded based on your results on this, but you can try it for fun.

### Your own tests

Feel free to add your own test files under the `tests` directory.