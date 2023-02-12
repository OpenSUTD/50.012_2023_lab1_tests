# 50.012 Networks Lab 1 Test Suite

This project implements an automated test suite for the HTTP proxy lab. It spins up a few test web servers in a docker network and a test monitor that starts new instances of your proxies on demand. Finally there is a run-once docker container containing a pytest suite that that communicates with the monitor to test your proxy. All these docker containers are orchestrated as a single docker-compose project.

## Usage

### Installing your proxy code

Place your proxy Python files inside `proxy/app` (create the folder if it doesn't exist). You can have as many files as you like but your application must conform to the following requirements:

- There must be a `proxy.py` file as this will be the entrypoint called by the monitor.
- Your application must start the proxy on port `8080` when no arguments are passed via the CLI.
- Your application must clear the contents of the cache folder (if you save it on disk) before serving clients on the HTTP proxy.
- Your application must handle `SIGINT` gracefully, releasing all resources and exiting within 5 seconds.

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

#### Proxy Monitor Log

The monitor is the process that runs your proxy repeatedly on demand. You can inspect the logs of the `proxy` container (`docker compose logs proxy`) to check for any abnormalities, such as detecting the TIME_WAIT bug (see below).

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

#### Test Client Hanging / TCP TIME_WAIT

If the client does not proceed for more than a minute, check the logs of the proxy container to see if the monitor has crashed. Your code might be suffering from the [TCP `TIME_WAIT` bug](http://hea-www.harvard.edu/~fine/Tech/addrinuse.html) if the monitor reports something like this in the logs:

```
WARNING: still found port used by process None in TIME_WAIT state
```

If the monitor has indeed crashed or stopped responding without any other errors, it might be a bug in the monitor. Raise issue on Github & contact your TA.

In any case, if you need to force abort the test, you can stop the test-client container, then stop the proxy container, then restart the proxy container, and finally restart the test-client container when you are ready.

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

## Development

First developed by Chester Koh for the Spring 2023 Term.

### Things to update for future batches

- More basic tests, such as caching query parameters
- Bonus tests for extra features like ETAG and HTTPS
- Test downloads of large files (scale of megabytes)
- Test for TIME_WAIT bug
- Rename the `proxy` service in docker compose to `proxy-monitor` for avoidance of doubt.