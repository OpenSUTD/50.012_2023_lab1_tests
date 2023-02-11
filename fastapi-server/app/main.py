import json
import time

import aiofiles
from fastapi import FastAPI, Body, Request, Response
from starlette.middleware.base import _StreamingResponse

app = FastAPI()


@app.middleware("http")
async def add_to_log(request: Request, call_next):
    response: _StreamingResponse = await call_next(request)

    async with aiofiles.open("/var/log/fastapi/access.log", "a") as f:
        log_entry = {
            "time": time.time(),
            "request_line": "{} {} {}".format(request.method.upper(), request.url, "HTTP/1.1"),
            "remote": request.client.host + ":{}".format(
                request.client.port) if request.client.port is not None else "",
            "status": response.status_code,
            # "response_hash": hashlib.md5(body).digest()
        }
        await f.write(json.dumps(log_entry) + "\n")
    return response


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/empty_body")
def empty_body():
    return Response(status_code=200)


@app.get("/test_query_parameters")
def test_query_parameters(deez: str, nuts: str):
    return "idk"


@app.post("/test_post")
def test_post(hello: str = Body()):
    return "You just posted something"


@app.get("/really_big_header")
def really_big_header(response: Response):
    for i in range(1024):
        response.headers[f"X-REALLY-BIG-HEADER-{i}"] = "ha" * 16
    return "You just got big 4head haha"


@app.get("/你好")
def test_chinese():
    return "Today is very 风和日丽"
