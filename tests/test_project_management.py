import os
import tempfile
import subprocess
import time
import shutil
import requests
import pytest

from test_utils import mcp_create_project, mcp_execute_shell


def get_json_headers():
    return {"Accept": "application/json", "Content-Type": "application/json"}


def build_tools_call_payload(name, arguments=None, id=1):
    p = {
        "jsonrpc": "2.0",
        "id": id,
        "method": "tools/call",
        "params": {"name": name},
    }
    if arguments is not None:
        p["params"]["arguments"] = arguments
    return p


@pytest.mark.usefixtures("mcp_server")
def test_get_active_project(mcp_server):
    """Verify that get_active_project returns the correct info after project creation."""
    project_name = "proj_active_test"
    mcp_create_project(mcp_server, project_name)
    headers = get_json_headers()
    payload = build_tools_call_payload("get_active_project", id=18)
    resp = requests.post(mcp_server, json=payload, headers=headers)
    assert resp.status_code == 200, f"get_active_project failed: {resp.text}"
    result = resp.json()["result"]
    struct = result.get("structuredContent")
    name = struct.get("name") if struct else result.get("name")
    path = struct.get("path") if struct else result.get("path")
    assert name == project_name, f"Active project mismatch: expected {project_name}, got {name!r}"
    assert path and path.endswith(project_name), f"Path mismatch: {path!r}"


@pytest.mark.usefixtures("mcp_server")
def test_change_active_project(mcp_server):
    """Verify that changing the active project works and is reflected everywhere."""
    project_a = "projA"
    project_b = "projB"
    mcp_create_project(mcp_server, project_a)
    mcp_create_project(mcp_server, project_b)
    headers = get_json_headers()
    change_payload = build_tools_call_payload(
        "change_active_project", arguments={"project_name": project_a}, id=30)
    resp = requests.post(mcp_server, json=change_payload, headers=headers)
    assert resp.status_code == 200, f"Change active project failed: {resp.text}"
    try:
        result = resp.json()["result"]["structuredContent"]["result"]
        assert result.startswith("Started shell for project: "), (
            f"Response did not start with expected text. resp.text={resp.text}"
        )
        assert project_a in result, f"Expected '{project_a}' in result. resp.text={resp.text}"
    except KeyError as e:
        raise AssertionError(f"KeyError {e} when accessing response JSON. Full response: {resp.text}") from e
    # Validate active project actually changed
    get_payload = build_tools_call_payload("get_active_project", id=31)
    get_resp = requests.post(mcp_server, json=get_payload, headers=headers)
    assert get_resp.status_code == 200
    result = get_resp.json()["result"]
    struct = result.get("structuredContent")
    name = struct.get("name") if struct else None
    assert name == project_a, f"Active project mismatch: expected {project_a}, got {name!r}"
    DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")
    echo_output = mcp_execute_shell(mcp_server, "echo $PWD")
    assert echo_output.endswith(f"{DEV_ROOT}/{project_a}"), f"Shell $PWD: got {echo_output!r}"
    # Create more projects, validate existence
    names = ["projA", "projB", "projC"]
    for n in names:
        mcp_create_project(mcp_server, n)
        assert os.path.isdir(os.path.join(DEV_ROOT, n)), f"Project dir not created for {n}"
    # List projects, validate all expected exist
    list_payload = build_tools_call_payload("list_all_projects", id=17)
    resp = requests.post(mcp_server, json=list_payload, headers=headers)
    assert resp.status_code == 200, f"List projects failed: {resp.text}"
    result = resp.json()["result"]
    if isinstance(result, dict) and "content" in result:
        project_names = [item.get("text") for item in result["content"] if isinstance(item, dict)]
    else:
        project_names = result
    assert set(names).issubset(set(project_names)), f"Projects missing: {names} not in {project_names}"


def start_server(projects_dir, port, default_project):
    """Start the server process with the given parameters."""
    return subprocess.Popen([
        "python", "-m", "mcp_grok.mcp_grok_server",
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


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
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
