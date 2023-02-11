import asyncio
import hashlib
import httpx
from typing import Callable, List, Coroutine


def test_empty_body(make_httpx_client: Callable[..., httpx.Client]):
    """
    I hope you didn't assume that the body always has something
    """
    client = make_httpx_client()
    response = client.request(
        method="GET",
        url="http://fastapi-server/empty_body"
    )
    assert response.status_code == 200
    assert len(response.read()) == 0


def test_really_big_header(make_httpx_client: Callable[..., httpx.Client]):
    """
    Did you assume that you could read the entire HTTP header in a single socket.recv(4096) call? Oops!
    """
    client = make_httpx_client()
    response = client.request(
        method="GET",
        url="http://fastapi-server/really_big_header"
    )
    for i in range(1024):
        assert f"X-REALLY-BIG-HEADER-{i}" in response.headers
        assert response.headers.get(f"X-REALLY-BIG-HEADER-{i}") == "ha" * 16

    assert response.read().decode() == """\"You just got big 4head haha\""""


def test_chinese(make_httpx_client: Callable[..., httpx.Client]):
    """
    Mr worldwide :)
    """
    client = make_httpx_client()
    response = client.request(
        method="GET",
        url="http://fastapi-server/你好"
    )
    assert response.read().decode() == """\"Today is very 风和日丽\""""


def test_cache_stampede_does_not_produce_corrupted_output(make_async_httpx_client: Callable[..., httpx.AsyncClient]):
    """
    What happens when a horde of elephants (I mean clients) rush to request the same resource from the proxy at once? Only one way to find out...
    """
    # try to find the original on disk
    with open(f"/var/html/home_igloo.gif", "rb") as f:
        md5_of_file_on_disk = hashlib.md5(f.read()).digest()
    clients: List[httpx.AsyncClient] = [make_async_httpx_client() for i in range(128)]

    async def make_get_request_and_return_hash(client: httpx.AsyncClient) -> bytes:
        response = await client.get("http://nginx-server/home_igloo.gif", timeout=60)
        return hashlib.md5(response.read()).digest()

    client_get_requests: List[Coroutine] = [make_get_request_and_return_hash(c) for c in clients]
    loop = asyncio.get_event_loop()
    gathered_task = asyncio.gather(*client_get_requests)
    loop.run_until_complete(gathered_task)
    result = gathered_task.result()
    for md5_of_response in result:
        assert md5_of_response == md5_of_file_on_disk
