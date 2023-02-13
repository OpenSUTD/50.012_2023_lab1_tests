import time
from os.path import isfile, join

import asyncio
import httpx
import os
import pytest
import socket
import zmq
from random import sample
from typing import Callable, List, Generator, Optional


@pytest.fixture(scope="session")
def proxy_host():
    return os.environ["PROXY_HOST"]


@pytest.fixture(scope="session")
def proxy_port():
    return int(os.environ["PROXY_PORT"])


@pytest.fixture(scope="session")
def proxy_address(proxy_host, proxy_port):
    return f"{proxy_host}:{proxy_port}"


@pytest.fixture()
def check_proxy_alive(proxy_host, proxy_port):
    def check_proxy_alive_closure():
        attempts = 1
        while attempts <= 10:
            try:
                with socket.create_connection((proxy_host, proxy_port), timeout=10):
                    return True
            except OSError:
                attempts += 1
                time.sleep(2)
        return False

    return check_proxy_alive_closure


@pytest.fixture(scope="session")
def zmq_socket(proxy_host):
    context = zmq.Context()
    _socket = context.socket(zmq.REQ)
    _socket.connect(f"tcp://{proxy_host}:5555")
    yield _socket
    _socket.close()
    context.term()


def try_and_get_response_from_zmq_server(zmq_socket: zmq.Socket, timeout: float) -> str:
    response = None
    time_elapsed = 0
    while response is None and time_elapsed < timeout:
        try:
            response = zmq_socket.recv(zmq.NOBLOCK).decode("utf-8")
        except zmq.ZMQError:
            time.sleep(0.2)
            time_elapsed += 0.1
            continue
    return response


premature_exit: bool = False


@pytest.fixture()
def restart_proxy(proxy_host, zmq_socket: zmq.Socket, request):
    def restart_proxy_closure():
        zmq_socket.send(f"begin_test {request.node.name}".encode("utf-8"))
        response = try_and_get_response_from_zmq_server(zmq_socket, 15)
        if response != "restarted":
            global premature_exit
            premature_exit = True
            pytest.exit("The proxy runner was not able to restart your proxy."
                        + " Check the logs of the proxy runner container and restart it if necessary.")

    return restart_proxy_closure


@pytest.fixture(scope="function", autouse=True)
def setup_proxy_per_test(proxy_host, proxy_port, check_proxy_alive, restart_proxy):
    restart_proxy()
    assert check_proxy_alive(), "The proxy does not seem to be running before the test starts"
    yield
    assert check_proxy_alive(), "The proxy seems to have died after running the tests"


@pytest.fixture(scope="session", autouse=True)
def cleanup(proxy_host, zmq_socket: zmq.Socket, request):
    def send_end_tests_message():
        if premature_exit:
            return
        zmq_socket.send(f"end_tests".encode("utf-8"))
        response = try_and_get_response_from_zmq_server(zmq_socket, 15)
        if response != "ended":
            pytest.exit("The proxy runner was not able to restart your proxy at the end of the test suite."
                        + " Check the logs of the proxy runner container and restart it if necessary.")

    request.addfinalizer(send_end_tests_message)


@pytest.fixture()
def make_httpx_client(proxy_address) -> Generator[Callable[..., httpx.Client], None, None]:
    clients: List[httpx.Client] = []

    def httpx_client_closure() -> httpx.Client:
        proxies = {
            "all://": f"http://{proxy_address}",
        }
        client = httpx.Client(proxies=proxies, timeout=5)
        clients.append(client)
        return client

    yield httpx_client_closure
    for client in clients:
        client.close()


@pytest.fixture()
def make_async_httpx_client(proxy_address) -> Generator[Callable[..., httpx.AsyncClient], None, None]:
    clients: List[httpx.AsyncClient] = []

    def httpx_client_closure() -> httpx.AsyncClient:
        proxies = {
            "all://": f"http://{proxy_address}",
        }
        client = httpx.AsyncClient(proxies=proxies, timeout=5)
        clients.append(client)
        return client

    yield httpx_client_closure
    loop = asyncio.new_event_loop()
    client_closing_coroutines = [loop.create_task(c.aclose()) for c in clients]
    loop.run_until_complete(asyncio.gather(*client_closing_coroutines))
    loop.close()


def nginx_list_static_files(n_samples: Optional[int]) -> List[str]:
    nginx_file_path = "/var/html"
    list_of_files = [f for f in os.listdir(nginx_file_path) if isfile(join(nginx_file_path, f))]
    if n_samples:
        return sample(list_of_files, n_samples)
    else:
        return list_of_files


def pytest_addoption(parser):
    parser.addoption(
        "--proxytest-nginx-static-files-n-samples",
        default=None,
        type=int,
        required=False,
        help="if set, samples n files for testing with the proxy"
    )


def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "nginx_static_file" in metafunc.fixturenames:
        n_samples = metafunc.config.getoption("--proxytest-nginx-static-files-n-samples")
        metafunc.parametrize("nginx_static_file", nginx_list_static_files(n_samples))
