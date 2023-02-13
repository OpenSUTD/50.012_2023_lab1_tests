import time

import hashlib
import httpx
import pytest
from math import floor
from typing import Callable

from testutils import get_nginx_log_entries_after_time


def test_request_neverssl_receives_response(make_httpx_client):
    client = make_httpx_client()
    response = client.request(
        method="GET",
        url="http://neverssl.com"
    )
    body = response.read().decode("utf8")
    assert "NeverSSL" in body


def test_request_nginx_receives_response(make_httpx_client: Callable[..., httpx.Client], check_proxy_alive):
    client = make_httpx_client()
    response = client.request(
        method="GET",
        url=f"http://nginx-server/"
    )
    body = response.read().decode("utf8")
    assert "netscape" in body


def test_request_nginx_body_unchanged(make_httpx_client: Callable[..., httpx.Client], nginx_static_file: str):
    """
    Tests that all files return the exact same value from disk
    :param make_httpx_client: pytest fixture, closure that produces a http client with the configured proxy
    :param nginx_every_file: pytest parametrized fixture, returns one filename at a time
    """
    client = make_httpx_client()
    response = client.request(
        method="GET",
        url=f"http://nginx-server/{nginx_static_file}"
    )
    md5_of_proxy_response = hashlib.md5(response.read()).digest()
    # try to find the original on disk
    with open(f"/var/html/{nginx_static_file}", "rb") as f:
        md5_of_file_on_disk = hashlib.md5(f.read()).digest()
    assert md5_of_proxy_response == md5_of_file_on_disk


@pytest.mark.parametrize("request_a,request_b,request_c",
                         [
                             ("", "", ""),
                             ("", "", "action.gif"),
                             ("", "", "404"),
                             ("", "action.gif", "action.gif"),
                             ("", "404", "404"),
                             ("404", "404", "404")
                         ],
                         ids=[
                             "all_request_index",
                             "first_two_index_last_one_200",
                             "first_two_index_last_one_404",
                             "first_index_last_two_200",
                             "first_index_last_two_404",
                             "all_404"
                         ])
def test_closing_one_client_does_not_affect_other_clients(make_httpx_client: Callable[..., httpx.Client],
                                                          request_a: str, request_b: str, request_c: str):
    """
    Tests that after two clients connect to the proxy and make requests, if one closes the other should not be affected
    :param make_httpx_client: pytest fixture, closure that produces a http client with the configured proxy
    """
    client_1 = make_httpx_client()
    client_1.request(method="GET", url=f"http://nginx-server/{request_a}")
    client_2 = make_httpx_client()
    client_2.request(method="GET", url=f"http://nginx-server/{request_b}")
    client_1.close()
    client_2.request(method="GET", url=f"http://nginx-server/{request_c}")


def test_multiple_calls_to_same_resource_should_be_cached_single_client(make_httpx_client: Callable[..., httpx.Client]):
    """
    Requesting the same resource twice should serve from the cache. We will assert from the NGINX logs that the upstream server (NGINX) only received one request from your proxy.
    :param make_httpx_client: pytest fixture, closure that produces a http client with the configured proxy
    """
    client = make_httpx_client()
    start_time = floor(time.time())
    client.request(method="GET", url=f"http://nginx-server/")
    time.sleep(1)
    client.request(method="GET", url=f"http://nginx-server/")
    relevant_log_entries = [l for l in get_nginx_log_entries_after_time(start_time) if
                            l["request_line"] == "GET http://nginx-server/ HTTP/1.1"]
    assert len(relevant_log_entries) == 1, "There must be exactly one request made after the start_time"


def test_cached_resources_should_be_namespaced_by_domain(make_httpx_client: Callable[..., httpx.Client]):
    """
    If I make a request to site-a.com/index.html and then a request to site-b.com/index.html, the contents should not be the same
    """
    client = make_httpx_client()
    response_a = client.get(url=f"http://nginx-server/")
    response_b = client.get(url=f"http://fastapi-server/")
    response_a_hash = hashlib.md5(response_a.read()).digest()
    response_b_hash = hashlib.md5(response_b.read()).digest()
    assert response_b_hash != response_a_hash
