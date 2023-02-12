import time

import psutil
import signal
import subprocess
import zmq
from typing import Optional

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

print("Bound ZMQ socket, launching idle proxy")


def kill_python_proxy(shell_pid: int):
    shell_process = psutil.Process(shell_pid)
    python_pid = None
    for child in shell_process.children():
        if "python" in child.cmdline():
            python_pid = child.pid
            child.send_signal(signal.SIGINT)
            time.sleep(5)
            child.terminate()
            time.sleep(5)
            child.kill()
    return python_pid


def wait_for_pid_exit(pid: int):
    while True:
        if pid not in psutil.pids():
            return
        time.sleep(1)


def wait_python_proxy_ready(pid: int):
    python_process = psutil.Process(pid)
    while True:
        python_connections = python_process.connections(kind="tcp4")
        for connection in python_connections:
            if connection.laddr.port == 8080:
                return
        time.sleep(0.1)


def launch_proxy_process(experiment_name: str) -> psutil.Process:
    logfile = f"/var/log/proxy/{experiment_name}.log"
    p = subprocess.Popen(f"exec python -u /app/proxy.py 2>&1 | ts > {logfile}", shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/app")
    return psutil.Process(p.pid)


def launch_proxy_and_wait(experiment_name: str) -> psutil.Process:
    shell_process = launch_proxy_process(experiment_name)
    print(f"Launched sh subprocess as {shell_process.pid}")
    while not shell_process.children():
        print("Wait for sh subprocess to spawn children...")
        time.sleep(0.2)
    python_process = next(filter(lambda cp: "python" in cp.name(), shell_process.children()))
    wait_python_proxy_ready(python_process.pid)
    print("Proxy ready")
    return shell_process


def shutdown_proxy_and_wait(shell_process):
    python_process = next(filter(lambda cp: "python" in cp.name(), shell_process.children()))
    print(f"Sending SIGINT to process {python_process.pid}")
    python_process.send_signal(signal.SIGINT)
    try:
        python_process.wait(5)
    except subprocess.TimeoutExpired:
        while python_process.is_running():
            print(f"Process {python_process.pid} is still running, sending SIGTERM")
            python_process.kill()
            time.sleep(1)
    # check if port 8080 is free
    connections = psutil.net_connections(kind="inet")
    port_available = None
    while port_available is None or port_available is False:
        port_available = True
        for connection in connections:
            if connection.laddr.port == 8080:
                print(f"WARNING: still found port used by process {connection.pid} in {connection.status} state")
                port_available = False
                time.sleep(1)
                break


current_shell_process: Optional[psutil.Process] = launch_proxy_and_wait(experiment_name="pre-experiment-idle")

while True:
    #  Wait for next request from client
    try:
        message_b = socket.recv(zmq.NOBLOCK)
    except zmq.ZMQError:
        dont_print_enter_loop = False
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            print("Received KeyboardInterrupt in main loop")
            break
        continue
    msg: str = message_b.decode("utf-8")
    code, data = msg.split(" ", maxsplit=1) if " " in msg else (msg, None)
    print("Received", code)
    if code == "begin_test":
        print("Beginning test: ", data)
        if current_shell_process is not None:
            shutdown_proxy_and_wait(current_shell_process)
        current_shell_process = launch_proxy_and_wait(experiment_name=data)
        socket.send("restarted".encode("utf-8"))
    elif code == "end_tests":
        if current_shell_process is not None:
            shutdown_proxy_and_wait(current_shell_process)
        current_shell_process = launch_proxy_and_wait(experiment_name="post-experiment-idle")
        socket.send("ended".encode("utf-8"))
    else:
        print("Received unknown message")
        socket.send(b"???")
    time.sleep(1)

print("Goodbye")
