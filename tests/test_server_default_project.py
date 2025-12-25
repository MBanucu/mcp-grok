import tempfile
import subprocess
import time
import os
import shutil
import requests


def start_server(projects_dir, port, default_project):
    """Start the server process with the given parameters."""
    return subprocess.Popen([
        "python", "-m", "src.server",
        "--port", str(port),
        "--projects-dir", projects_dir,
        "--default-project", default_project
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def wait_for_server_ready(server_proc, timeout=30):
    """Wait for server to indicate it is ready, or timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if server_proc.stdout is not None:
            ln = server_proc.stdout.readline()
            if not ln:
                if server_proc.poll() is not None:
                    raise RuntimeError(f"Server exited early: code {server_proc.returncode}")
                continue
            if (
                "Uvicorn running on http://" in ln or
                "Uvicorn running on http://127.0.0.1" in ln
            ):
                return True
        else:
            if server_proc.poll() is not None:
                raise RuntimeError("Server process exited prematurely (no stdout)")
            time.sleep(0.2)
    return False


def get_active_project(url, default_project, default_proj_path):
    """Request active project via API and validate response."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0", "id": 32177, "method": "tools/call",
        "params": {"name": "get_active_project"}
    }
    for _ in range(20):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=4)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.3)
    else:
        raise AssertionError("get_active_project did not succeed after retries")
    result = r.json()["result"]
    struct = result.get("structuredContent")
    if struct:
        name = struct.get("name")
        path = struct.get("path")
    else:
        name = result.get("name")
        path = result.get("path")
    assert name == default_project, (
        f"Expected active project '{default_project}', got '{name}'"
    )
    # Split assert for E501
    assert path, f"Active project path missing: got '{path}'"
    abs_path_actual = os.path.abspath(path)
    abs_path_expected = os.path.abspath(default_proj_path)
    assert abs_path_actual == abs_path_expected, (
        f"Active project path mismatch: got '{abs_path_actual}', expected '{abs_path_expected}'"
    )


def cleanup_server(server_proc, projects_dir):
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    shutil.rmtree(projects_dir, ignore_errors=True)


def test_default_project_activation():
    """
    Test that starting the server with --default-project activates/creates that project.
    """
    projects_dir = tempfile.mkdtemp(prefix="mcp-grok-defaultproj-")
    port = 8128
    default_project = "autotest_default_proj"
    server_proc = start_server(projects_dir, port, default_project)
    try:
        ready = wait_for_server_ready(server_proc)
        assert ready, "Timeout waiting for server startup"
        default_proj_path = os.path.join(projects_dir, default_project)
        assert os.path.isdir(
            default_proj_path
        ), f"Default project directory was not created: {default_proj_path}"
        url = f"http://localhost:{port}/mcp"
        get_active_project(url, default_project, default_proj_path)
    finally:
        cleanup_server(server_proc, projects_dir)
