import os
import shutil
import requests
import pytest
import getpass

PORT = 8099
RPC_ID_CREATE_PROJECT = 1
RPC_ID_EXECUTE_SHELL = 2
RPC_ID_GET_ACTIVE_PROJECT = 18
RPC_ID_CHANGE_ACTIVE_PROJECT = 30
RPC_ID_LIST_PROJECTS = 17
RPC_ID_ECHO_PWD = 32
USER_HOME = os.path.expanduser("~")
DEV_ROOT = os.path.join(USER_HOME, "dev", "mcp-projects-test")

# --- Fixtures & Helpers ---


@pytest.fixture(scope="module")
def mcp_server():
    import subprocess
    import time
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)
    os.makedirs(DEV_ROOT, exist_ok=True)
    server_proc = subprocess.Popen([
        "uv", "run", "python", "-m", "server", "--port", str(PORT), "--projects-dir", DEV_ROOT
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    start_time = time.time()
    while True:
        if server_proc.poll() is not None:
            raise RuntimeError("Server process exited prematurely")
        if server_proc.stdout is not None:
            line = server_proc.stdout.readline()
            if "Uvicorn running on http://" in line:
                break
        else:
            import time as _t
            _t.sleep(0.1)
        if time.time() - start_time > 30:
            raise TimeoutError("Timed out waiting for server readiness")
    yield f"http://localhost:{PORT}/mcp"
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)


# --- Internal Helpers ---

def mcp_create_project(server_url, project_name):
    """Create project via MCP API."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_CREATE_PROJECT,
        "method": "tools/call",
        "params": {
            "name": "create_new_project",
            "arguments": {"project_name": project_name},
        },
    }
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    data = resp.json()
    assert "result" in data, f"JSON-RPC error or missing result: {data}"
    test_dir = os.path.join(DEV_ROOT, project_name)
    assert os.path.isdir(test_dir), f"Project dir not created: {test_dir}"
    return test_dir


def mcp_execute_shell(server_url, command):
    """Run shell command via MCP API."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_EXECUTE_SHELL,
        "method": "tools/call",
        "params": {
            "name": "execute_shell",
            "arguments": {"command": command},
        },
    }
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"Shell failed: {resp.text}"
    data = resp.json()
    return _extract_shell_output(data["result"])


def _extract_shell_output(result):
    content = result.get("content", result) if isinstance(result, dict) else result
    if isinstance(content, list):
        return "\n".join(
            item.get("text", str(item)) for item in content if isinstance(item, dict)
        ).strip()
    return str(content).strip()


def get_last_non_empty_line(output):
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""

# --- Test Cases ---


def test_shell_echo_path(mcp_server):
    """Echo $PATH env var, must contain ':' ."""
    project_name = "pytest_echo_path"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'echo "$PATH"')
    last_line = get_last_non_empty_line(shell_output)
    assert last_line, f"$PATH empty: {last_line!r}"
    assert ':' in last_line, f"$PATH missing ':': {last_line!r}"


def test_shell_echo_user(mcp_server):
    """Check shell user matches getpass.getuser."""
    project_name = "pytest_echo_user"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'whoami')
    last_line = get_last_non_empty_line(shell_output)
    expected_user = getpass.getuser()
    assert last_line == expected_user, f"User mismatch: expected {expected_user}, got {last_line!r}"


def test_shell_detect_nix_shell(mcp_server):
    """Should say NOT in nix-shell."""
    project_name = "pytest_nixshell"
    mcp_create_project(mcp_server, project_name)
    shell_script = '''
    if [[ -n "$IN_NIX_SHELL" ]]; then
        echo "Inside nix-shell ($IN_NIX_SHELL)"
    else
        echo "Not inside nix-shell"
    fi
    '''.strip()
    shell_output = mcp_execute_shell(mcp_server, shell_script)
    last_line = get_last_non_empty_line(shell_output)
    assert "Not inside nix-shell" in last_line, f"Expected outside nix-shell, got: {last_line!r}"


def test_get_active_project(mcp_server):
    """API: get_active_project returns correct name/path."""
    project_name = "proj_active_test"
    mcp_create_project(mcp_server, project_name)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_GET_ACTIVE_PROJECT,
        "method": "tools/call",
        "params": {"name": "get_active_project"},
    }
    resp = requests.post(mcp_server, json=payload, headers=headers)
    assert resp.status_code == 200, f"get_active_project failed: {resp.text}"
    result = resp.json()["result"]
    struct = result.get("structuredContent")
    name = struct.get("name") if struct else result.get("name")
    path = struct.get("path") if struct else result.get("path")
    assert name == project_name, f"Active project mismatch: expected {project_name}, got {name!r}"
    assert path and path.endswith(project_name), f"Path mismatch: {path!r}"


def test_change_active_project(mcp_server):
    """Change active project; verify $PWD/project listing."""
    project_a = "projA"
    project_b = "projB"
    mcp_create_project(mcp_server, project_a)
    mcp_create_project(mcp_server, project_b)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    change_payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_CHANGE_ACTIVE_PROJECT,
        "method": "tools/call",
        "params": {"name": "change_active_project", "arguments": {"project_name": project_a}},
    }
    resp = requests.post(mcp_server, json=change_payload, headers=headers)
    assert resp.status_code == 200, f"Change active project failed: {resp.text}"
    try:
        result = resp.json()["result"]["structuredContent"]["result"]
        assert result.startswith(f"Started shell for project: "), f"Response did not start with expected text. resp.text={resp.text}"
        assert project_a in result, f"Expected '{project_a}' in result. resp.text={resp.text}"
    except KeyError as e:
        raise AssertionError(f"KeyError {e} when accessing response JSON. Full response: {resp.text}") from e
    get_payload = {
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {"name": "get_active_project"},
    }
    get_resp = requests.post(mcp_server, json=get_payload, headers=headers)
    assert get_resp.status_code == 200
    result = get_resp.json()["result"]
    struct = result.get("structuredContent")
    name = struct.get("name") if struct else None
    assert name == project_a, f"Active project mismatch: expected {project_a}, got {name!r}"
    echo_output = mcp_execute_shell(mcp_server, "echo $PWD")
    assert echo_output.endswith(f"{DEV_ROOT}/{project_a}"), f"Shell $PWD: got {echo_output!r}"
    # Create and check multiple projects
    names = ["projA", "projB", "projC"]
    for n in names:
        mcp_create_project(mcp_server, n)
        assert os.path.isdir(os.path.join(DEV_ROOT, n)), f"Project dir not created for {n}"
    list_payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_LIST_PROJECTS,
        "method": "tools/call",
        "params": {"name": "list_all_projects"},
    }
    resp = requests.post(mcp_server, json=list_payload, headers=headers)
    assert resp.status_code == 200, f"List projects failed: {resp.text}"
    result = resp.json()["result"]
    if isinstance(result, dict) and "content" in result:
        project_names = [item.get("text") for item in result["content"] if isinstance(item, dict)]
    else:
        project_names = result
    assert set(names).issubset(set(project_names)), f"Projects missing: {names} not in {project_names}"


def test_shell_double_pipe_or(mcp_server):
    """Test shell fallback with '||'."""
    project_name = "pytest_shell_double_pipe_or"
    mcp_create_project(mcp_server, project_name)
    # Command succeeds
    out1 = mcp_execute_shell(mcp_server, 'echo foo || echo bar')
    assert any("foo" in line for line in out1.splitlines()), f"Expected 'foo', got: {out1!r}"
    assert not any("bar" in line for line in out1.splitlines()), f"Unexpected 'bar': {out1!r}"
    # Command fails
    out2 = mcp_execute_shell(mcp_server, 'false || echo fallback')
    assert any("fallback" in line for line in out2.splitlines()), f"Expected 'fallback', got: {out2!r}"
    assert not any("foo" in line for line in out2.splitlines()), f"Unexpected 'foo': {out2!r}"


def test_shell_ls_or_echo(mcp_server):
    """Test 'ls' fallback to echo if dir missing."""
    project_name = "pytest_shell_ls_or_echo"
    mcp_create_project(mcp_server, project_name)
    cmd = 'ls -l /run/opengl-driver/lib/ 2>/dev/null || echo "Directory not found or empty"'
    shell_output = mcp_execute_shell(mcp_server, cmd)
    assert shell_output.strip(), "Shell output should not be empty."
    if "Directory not found or empty" in shell_output:
        assert shell_output.strip() == "Directory not found or empty", f"Fallback expected, got: {shell_output!r}"
    else:
        # Directory listing expected
        assert any(
            line.strip().startswith(("d", "l", "-", "total"))
            for line in shell_output.splitlines()
        ), f"Expected dir listing, got: {shell_output!r}"
