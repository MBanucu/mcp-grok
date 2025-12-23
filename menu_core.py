import os
import subprocess

MCP_LOGFILE = "mcp_server.log"
PROXY_LOGFILE = "superassistant_proxy.log"

def start_server():
    log = open(MCP_LOGFILE, "a")
    proc = subprocess.Popen(
        ['uv', 'run', 'server.py'],
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        env={**os.environ, 'NO_COLOR': '1'},
    )
    return proc

def stop_server(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

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
