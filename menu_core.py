import os
import subprocess
import socket

MCP_LOGFILE = "mcp_server.log"
PROXY_LOGFILE = "superassistant_proxy.log"


class ServerManager:
    def __init__(self):
        self._server_proc = None
    def start_server(self, port=8000):
        # Check if server is already running on the given port
        try:
            with socket.create_connection(('localhost', port), timeout=2):
                # If we started the process and it is still running, return it
                if self._server_proc is not None and self._server_proc.poll() is None:
                    print(f"Server is already running (started by this process) on port {port}.")
                    return self._server_proc
                # Otherwise, server is running but was not started by us
                print(f"Server is already running on port {port}.")
                return None
        except (ConnectionRefusedError, OSError):
            # Server is not running
            pass

        log = open(MCP_LOGFILE, "a")
        proc = subprocess.Popen(
            ['python', '-m', 'src.server', '--port', str(port)],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            env={**os.environ, 'NO_COLOR': '1'},
        )
        self._server_proc = proc
        return proc

    def stop_server(self):
        p = self._server_proc
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        self._server_proc = None

server_manager = ServerManager()


def start_proxy():
    log = open(PROXY_LOGFILE, "a")
    proc = subprocess.Popen(
        ['superassistant-proxy'],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        close_fds=True,
        env={**os.environ, 'NO_COLOR': '1'},
    )
    return proc

def stop_proxy(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

def clear_log(log_path):
    if os.path.exists(log_path):
        with open(log_path, "w"): pass

def log_content(log_path):
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return f.read()
    return None
