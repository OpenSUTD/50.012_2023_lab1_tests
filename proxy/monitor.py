import psutil
import subprocess
import time
import zmq

context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")

print("Bound ZMQ socket, launching idle proxy")
logfile = f"/var/log/proxy/idle-{round(time.time())}.log"
p = subprocess.Popen(f"exec python -u /app/proxy.py 2>&1 | ts", shell=True, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL, cwd="/app")

print("Idle proxy launched - PID", p.pid)


def kill_python_proxy(shell_pid: int):
    shell_process = psutil.Process(shell_pid)
    python_pid = None
    for child in shell_process.children():
        if "python" in child.cmdline():
            python_pid = child.pid
            child.kill()
    return python_pid


def wait_for_pid_exit(pid: int):
    while True:
        if pid not in psutil.pids():
            return
        time.sleep(1)


def wait_python_proxy(shell_pid: int):
    shell_process = psutil.Process(shell_pid)
    python_pid = None
    while True:
        for child in shell_process.children():
            if "python" in child.cmdline():
                python_pid = child.pid
                break
        if python_pid:
            break
        time.sleep(0.1)
    python_process = psutil.Process(python_pid)
    while True:
        python_connections = python_process.connections(kind="tcp4")
        for connection in python_connections:
            if connection.laddr.port == 8080:
                return
        time.sleep(0.1)


while True:
    print("Enter loop")
    #  Wait for next request from client
    message_b = socket.recv()
    msg: str = message_b.decode("utf-8")
    code, data = msg.split(" ", maxsplit=1) if " " in msg else (msg, None)
    print("Received", code)
    if code == "begin_test":
        print("Beginning test function: ", data)
        try:
            python_proxy_pid = kill_python_proxy(p.pid)
        except psutil.NoSuchProcess:
            pass
        wait_for_pid_exit(python_proxy_pid)
        p.kill()
        wait_for_pid_exit(p.pid)
        logfile = f"/var/log/proxy/{data}.log"
        p = subprocess.Popen(f"exec python -u /app/proxy.py 2>&1 | ts > {logfile}", shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/app")
        wait_python_proxy(p.pid)
        socket.send("restarted".encode("utf-8"))
    elif code == "end_tests":
        print("Ending test suite, returning to idle state")
        try:
            python_proxy_pid = kill_python_proxy(p.pid)
        except psutil.NoSuchProcess:
            pass
        wait_for_pid_exit(python_proxy_pid)
        p.kill()
        wait_for_pid_exit(p.pid)
        # logfile = f"/var/log/proxy/idle-{round(time.time())}.log"
        # p = subprocess.Popen(f"exec python -u /app/proxy.py 2>&1 | ts", shell=True, stdout=subprocess.DEVNULL,
        #                      stderr=subprocess.DEVNULL, cwd="/app")
        # wait_python_proxy(p.pid)
        socket.send(b"ended")
    else:
        print("Received unknown message")
        socket.send(b"???")
    time.sleep(1)
