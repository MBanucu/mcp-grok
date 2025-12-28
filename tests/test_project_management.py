import os
import tempfile
import subprocess
import time
import shutil
import threading
import queue
import requests
import pytest
import contextlib

from test_utils import mcp_create_project, mcp_execute_shell

# =====================
# Tests (top-level only one abstraction)
# =====================


@pytest.mark.usefixtures("mcp_server")
def test_get_active_project(mcp_server):
    """Should set and fetch the active project info after creation."""
    project_name = "proj_active_test"
    mcp_create_project(mcp_server, project_name)
    _assert_active_project_name(mcp_server, project_name)


@pytest.mark.usefixtures("mcp_server")
def test_change_active_project(mcp_server):
    """Should change active project, reflect in shell, and show all projects as present."""
    project_a = "projA"
    project_b = "projB"
    _make_projects(mcp_server, [project_a, project_b])
    _change_active_project(mcp_server, project_a)
    _assert_active_project_name(mcp_server, project_a)
    _assert_shell_cwd_matches(mcp_server, project_a)
    all_projects = [project_a, project_b, "projC"]
    _make_projects(mcp_server, ["projC"])
    _assert_project_dirs_exist(all_projects)
    _assert_listed_projects_superset(mcp_server, all_projects)


def test_default_project_activation():
    """Should activate default project on server startup, with robust log capture."""
    with _running_server_with_default_project() as (server_url, default_project, project_path, log_buffer):
        _assert_active_project_api(server_url, default_project, project_path)
        # log_buffer now available for additional asserts if desired


# =====================
# Test helpers (one abstraction each)
# =====================


def _assert_active_project_name(server, name):
    result = _get_active_project_result(server)
    actual = _extract_project_name(result)
    assert actual == name, f"Active project mismatch: expected {name}, got {actual!r}"
    assert _extract_project_path(result).endswith(name), f"Path does not end with {name}: {_extract_project_path(result)!r}"


def _assert_active_project_api(server_url, expected_name, expected_path):
    result = _get_active_project_result(server_url)
    actual_name = _extract_project_name(result)
    actual_path = _extract_project_path(result)
    assert actual_name == expected_name, (
        f"Active project name mismatch: expected {expected_name!r}, "
        f"got {actual_name!r}. Full result: {result!r}"
    )
    assert actual_path == expected_path, (
        f"Active project path mismatch: expected {expected_path!r}, "
        f"got {actual_path!r}. Full result: {result!r}"
    )


def _change_active_project(server, name):
    resp = requests.post(server, json=_build_tools_call_payload(
        "change_active_project", {"project_name": name}, id=30), headers=_json_headers())
    assert resp.status_code == 200, f"Change active project failed: {resp.text}"
    result = resp.json()["result"]["structuredContent"]["result"]
    assert result.startswith("Started shell for project: ")
    assert name in result


def _assert_shell_cwd_matches(server, project_name):
    DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")
    echo_output = mcp_execute_shell(server, "echo $PWD")
    assert echo_output.endswith(f"{DEV_ROOT}/{project_name}"), f"Shell $PWD: got {echo_output!r}"


def _make_projects(server, projects):
    for p in projects:
        mcp_create_project(server, p)


def _assert_project_dirs_exist(names):
    DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")
    for n in names:
        assert os.path.isdir(os.path.join(DEV_ROOT, n)), f"Project dir not created for {n}"


def _assert_listed_projects_superset(server, names):
    payload = _build_tools_call_payload("list_all_projects", id=17)
    resp = requests.post(server, json=payload, headers=_json_headers())
    assert resp.status_code == 200, f"List projects failed: {resp.text}"
    result = resp.json()["result"]
    listed = [item.get("text") for item in result["content"] if isinstance(item, dict)] \
        if isinstance(result, dict) and "content" in result else result
    assert set(names).issubset(set(listed)), (
        f"Projects missing: {names} not in {listed}"
    )


def _get_active_project_result(server):
    payload = _build_tools_call_payload("get_active_project", id=42)
    resp = requests.post(server, json=payload, headers=_json_headers())
    assert resp.status_code == 200, f"get_active_project failed: {resp.text}"
    return resp.json()["result"]


def _extract_project_name(result):
    struct = result.get("structuredContent")
    return struct.get("name") if struct else result.get("name")


def _extract_project_path(result):
    struct = result.get("structuredContent")
    return struct.get("path") if struct else result.get("path")


@contextlib.contextmanager
def _running_server_with_default_project(port=8128):
    projects_dir = tempfile.mkdtemp(prefix="mcp-grok-defaultproj-")
    default_project = "autotest_default_proj"
    project_path = os.path.join(projects_dir, default_project)
    log_buffer = []
    proc, out_queue, tee_thread = _start_server(projects_dir, port, default_project, log_buffer)
    try:
        ready = _wait_for_server_ready(proc, out_queue)
        assert ready, "Timeout waiting for server startup"
        url = f"http://localhost:{port}/mcp"
        yield url, default_project, project_path, log_buffer
    finally:
        _cleanup_server(proc, projects_dir, log_buffer)


def tee_server_stdout(proc, out_queue, log_buffer):
    def _reader():
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            print(line, end='')
            out_queue.put(line)
            log_buffer.append(line)
    t = threading.Thread(target=_reader, daemon=True)
    t.start()
    return t


def _start_server(projects_dir, port, default_project, log_buffer):
    proc = subprocess.Popen([
        "python", "-m", "mcp_grok.mcp_grok_server",
        "--port", str(port),
        "--projects-dir", projects_dir,
        "--default-project", default_project
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    out_queue = queue.Queue()
    tee_thread = tee_server_stdout(proc, out_queue, log_buffer)
    return proc, out_queue, tee_thread


def _wait_for_server_ready(proc, out_queue, timeout=30):
    t0 = time.time()
    ready = False
    while time.time() - t0 < timeout:
        try:
            line = out_queue.get(timeout=0.5)
            if "Uvicorn running on http://" in line or "Uvicorn running on http://127.0.0.1" in line:
                ready = True
                break
        except queue.Empty:
            if proc.poll() is not None:
                break
    return ready


def _cleanup_server(server_proc, projects_dir, log_buffer=None):
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    if getattr(server_proc, "stdout", None):
        server_proc.stdout.close()
    if server_proc.returncode not in (0, None):
        print("\n======= MCP SERVER PROCESS OUTPUT (on error) =======")
        if log_buffer:
            print("".join(log_buffer))
        else:
            print("(No output)")
        print("======= END OF MCP SERVER OUTPUT =======")
    shutil.rmtree(projects_dir, ignore_errors=True)


# =====================
# Pure utilities (lowest level)
# =====================


def _json_headers():
    return {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def _build_tools_call_payload(name, arguments=None, id=1):
    p = {
        "jsonrpc": "2.0",
        "id": id,
        "method": "tools/call",
        "params": {"name": name},
    }
    if arguments is not None:
        p["params"]["arguments"] = arguments
    return p
