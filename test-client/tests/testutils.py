import json
from math import floor
from typing import List, Dict, Any


def get_nginx_log_entries_after_time(time: float | int) -> List[Dict[str, Any]]:
    start_time = floor(time)
    with open("/var/log/nginx/access.log", "r") as f:
        while True:
            line = f.readline().strip()
            if not line:
                assert False, "Did not seem to find a future log entry in nginx after firing the request"
            log_object = json.loads(line)
            if log_object["time"] >= start_time:
                log_entries = [log_object] + [json.loads(s) for s in f.readlines()]
                return log_entries


def get_fastapi_log_entries_after_time(time: float | int) -> List[Dict[str, Any]]:
    start_time = floor(time)
    with open("/var/log/fastapi/access.log", "r") as f:
        while True:
            line = f.readline().strip()
            if not line:
                assert False, "Did not seem to find a future log entry in nginx after firing the request"
            log_object = json.loads(line)
            if log_object["time"] >= start_time:
                log_entries = [log_object] + [json.loads(s) for s in f.readlines()]
                return log_entries
