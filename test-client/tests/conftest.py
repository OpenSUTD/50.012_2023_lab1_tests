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


@pytest.fixture()
def restart_proxy(proxy_host, request):
    def restart_proxy_closure():
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://{proxy_host}:5555")
        socket.send(f"begin_test {request.node.name}".encode("utf-8"))
        response = socket.recv().decode("utf-8")
        assert response == "restarted"
        socket.close()

    return restart_proxy_closure


@pytest.fixture(scope="function", autouse=True)
def setup_proxy_per_test(proxy_host, proxy_port, check_proxy_alive, restart_proxy):
    restart_proxy()
    assert check_proxy_alive()
    yield
    assert check_proxy_alive()


@pytest.fixture(scope="session", autouse=True)
def cleanup(proxy_host, request):
    def send_end_tests_message():
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(f"tcp://{proxy_host}:5555")
        socket.send(f"end_tests".encode("utf-8"))
        socket.close()

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
