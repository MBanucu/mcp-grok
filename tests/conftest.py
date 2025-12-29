import os
import pytest

import socket

from mcp_grok.config import config


def pick_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = pick_free_port()
DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")


def setup_project_dir():
    import shutil
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)
    os.makedirs(DEV_ROOT, exist_ok=True)


def start_mcp_server():
    import subprocess
    return subprocess.Popen([
        "mcp-grok-server", "--port", str(PORT), "--projects-dir", DEV_ROOT
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def wait_for_mcp_server(server_proc, timeout=30):
    import time
    start_time = time.time()
    output_lines = []
    while True:
        if server_proc.poll() is not None:
            # Server crashed, print all output that was produced
            if server_proc.stdout is not None:
                more_output = server_proc.stdout.read()
                if more_output:
                    output_lines.append(more_output)
            output = "".join(output_lines)
            print("\n[SERVER STARTUP FAILED] Full server output:\n" + output)
            raise RuntimeError("Server process exited prematurely. See server logs above for reason.")
        if server_proc.stdout is not None:
            line = server_proc.stdout.readline()
            if line:
                output_lines.append(line)
            if "Uvicorn running on http://" in line:
                break
        else:
            time.sleep(0.1)
        if time.time() - start_time > timeout:
            output = "".join(output_lines)
            print("\n[SERVER STARTUP TIMEOUT] Full server output so far:\n" + output)
            raise TimeoutError("Timed out waiting for server readiness. See server logs above for reason.")


def teardown_mcp_server(server_proc):
    import shutil
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    if server_proc.stdout:
        server_proc.stdout.close()
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)


@pytest.fixture(scope="session", autouse=True)
def ensure_log_dirs():
    """Ensure parent directories for configured log files exist for tests."""
    try:
        os.makedirs(os.path.dirname(config.mcp_shell_log), exist_ok=True)
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(config.proxy_log), exist_ok=True)
    except Exception:
        pass


@pytest.fixture(scope="session")
def mcp_server():
    setup_project_dir()
    server_proc = start_mcp_server()
    wait_for_mcp_server(server_proc)
    yield f"http://localhost:{PORT}/mcp"
    teardown_mcp_server(server_proc)
