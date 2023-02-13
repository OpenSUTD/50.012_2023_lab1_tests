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


def wait_python_proxy_ready(pid: int):
    python_process = psutil.Process(pid)
    time_elapsed = 0
    while True:
        python_connections = python_process.connections(kind="tcp4")
        for connection in python_connections:
            if connection.laddr.port == 8080:
                return
        time.sleep(0.1)
        if time_elapsed >= 10:
            raise TimeoutError("Python proxy did not managed to bind to port 8080 after waiting 10 seconds. "
                               "Check the individual log file.")


def launch_proxy_process(experiment_name: str) -> psutil.Process:
    logfile = f"/var/log/proxy/{experiment_name}.log"
    p = subprocess.Popen(f"exec python -u /app/proxy.py 2>&1 | ts > {logfile}", shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/app")
    return psutil.Process(p.pid)


def launch_proxy_and_wait(experiment_name: str) -> psutil.Process:
    shell_process = launch_proxy_process(experiment_name)
    print(f"Launched sh subprocess as {shell_process.pid}")
    attempts = 0
    while not shell_process.children():
        print("Wait for sh subprocess to spawn children...")
        time.sleep(0.2)
        attempts += 1
        if attempts > 10:
            raise TimeoutError("sh subprocess did not spawn children after a reasonable time. "
                               "Check if proxy.py exists in the app folder.")
    try:
        python_process = next(filter(lambda cp: "python" in cp.name(), shell_process.children()))
    except StopIteration:
        raise Exception(f"Could not find a python child process - it might have died immediately."
                        f"Check the log file {experiment_name}.log")
    wait_python_proxy_ready(python_process.pid)
    print("Proxy ready")
    return shell_process


def shutdown_proxy_and_wait(shell_process: psutil.Process):
    python_process = next(filter(lambda cp: "python" in cp.name(), shell_process.children()))
    print(f"Sending SIGINT to process {python_process.pid}")
    python_process.send_signal(signal.SIGINT)
    time_elapsed = 0
    while python_process.is_running() and time_elapsed < 5:
        time.sleep(0.1)
        time_elapsed += 0.1
    while python_process.is_running():
        print(f"Process {python_process.pid} is still running, sending SIGTERM")
        python_process.kill()
        time.sleep(1)
    # check if port 8080 is free
    port_available = None
    time_elapsed = 0
    while port_available is None or port_available is False:
        port_available = True
        for connection in psutil.net_connections(kind="inet"):
            if connection.laddr.port == 8080:
                print(f"WARNING: still found port used by process {connection.pid} in {connection.status} state. "
                      "Retrying in 5 seconds...")
                if connection.pid is None:
                    print("WARNING: netstat reports the port is being used by an exited process - "
                          "did you close your sockets on program exit??")
                port_available = False
                time.sleep(1)
                time_elapsed += 1
                break
        if time_elapsed > 5:
            raise TimeoutError("Port was still not free after 5 seconds :(")


current_shell_process: Optional[psutil.Process] = None

try:
    current_shell_process: Optional[psutil.Process] = launch_proxy_and_wait(experiment_name="pre-experiment-idle")
except Exception as ex:
    print("FATAL: Could not start the proxy before experiment starts:")
    print(str(ex))
    print("The proxy runner will still be available, "
          "but it is recommended to investigate and replace the proxy.py file.")

sigterm_caught = False


def on_sigterm(signum, frame):
    global sigterm_caught
    print("Caught sigterm")
    sigterm_caught = True


signal.signal(signal.SIGTERM, on_sigterm)
should_say_waiting = True
while not sigterm_caught:
    #  Wait for next request from client
    if should_say_waiting:
        print("Waiting for command on ZMQ socket...")
        should_say_waiting = False
    try:
        message_b = socket.recv(zmq.NOBLOCK)
    except zmq.ZMQError:
        time.sleep(1)
        continue
    should_say_waiting = True
    msg: str = message_b.decode("utf-8")
    code, data = msg.split(" ", maxsplit=1) if " " in msg else (msg, None)
    print("Received", code)
    if code == "begin_test":
        print("Beginning test: ", data)
        if current_shell_process is not None:
            try:
                shutdown_proxy_and_wait(current_shell_process)
            except TimeoutError as ex:
                print("Could not kill the existing proxy instance at the start of test:")
                print(str(ex))
                socket.send("could_not_end".encode("utf-8"))
                current_shell_process = None
                continue
        try:
            current_shell_process = launch_proxy_and_wait(experiment_name=data)
        except Exception as ex:
            print("Could not start a new instance of the proxy at proxy at the start of the test")
            print(str(ex))
            socket.send("ended_but_could_not_restart".encode("utf-8"))
            continue
        socket.send("restarted".encode("utf-8"))
    elif code == "end_tests":
        if current_shell_process is not None:
            try:
                shutdown_proxy_and_wait(current_shell_process)
            except TimeoutError as ex:
                print("Could not kill the proxy instance at the end of test suite:")
                print(str(ex))
                socket.send("could_not_end".encode("utf-8"))
                current_shell_process = None
                continue
        try:
            current_shell_process = launch_proxy_and_wait(experiment_name="post-experiment-idle")
        except Exception as ex:
            print("Could not start a new instance of the proxy at the end of experiments:")
            print(str(ex))
            socket.send("ended_but_could_not_restart".encode("utf-8"))
            continue
        socket.send("ended".encode("utf-8"))
    else:
        print("Received unknown message")
        socket.send(b"???")

print("Closing ZMQ server socket")
socket.close()
print("Closing ZMQ server context")
context.term()
print("Goodbye")
