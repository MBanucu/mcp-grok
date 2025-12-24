import os
import subprocess
import time
import shutil
import requests
import select
import pytest

PORT = 8099
RPC_ID_CREATE_PROJECT = 1
RPC_ID_EXECUTE_SHELL = 2
RPC_ID_GET_ACTIVE_PROJECT = 18
RPC_ID_CHANGE_ACTIVE_PROJECT = 30
RPC_ID_LIST_PROJECTS = 17
RPC_ID_ECHO_PWD = 32
USER_HOME = os.path.expanduser("~")
DEV_ROOT = os.path.join(USER_HOME, "dev", "mcp-projects-test")

# Helper
def wait_for_server_ready(server_proc, timeout=30):
    start_time = time.time()
    if server_proc.stdout is None:
        server_proc.terminate()
        raise RuntimeError("Failed to capture server stdout")
    while True:
        if time.time() - start_time > timeout:
            server_proc.terminate()
            raise TimeoutError("Timed out waiting for server to start")
        rlist, _, _ = select.select([server_proc.stdout], [], [], 0.1)
        if rlist:
            line = server_proc.stdout.readline()
            if not line:
                if server_proc.poll() is not None:
                    raise RuntimeError("Server process exited prematurely")
                continue
            if "Uvicorn running on http://" in line or "Uvicorn running on http://127.0.0.1" in line:
                return

@pytest.fixture(scope="module")
def mcp_server():
    # Clean dev root
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)
    os.makedirs(DEV_ROOT, exist_ok=True)
    # Start server
    server_proc = subprocess.Popen([
        "python", "-m", "src.server", "--port", str(PORT), "--projects-dir", DEV_ROOT],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_server_ready(server_proc)
        yield f"http://localhost:{PORT}/mcp"
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()
        if os.path.exists(DEV_ROOT):
            shutil.rmtree(DEV_ROOT)

def mcp_create_project(server_url, project_name):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    create_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_new_project",
            "arguments": {"project_name": project_name}
        }
    }
    create_resp = requests.post(server_url, json=create_payload, headers=headers)
    assert create_resp.status_code == 200, f"Failed: {create_resp.text}"
    create_data = create_resp.json()
    assert "result" in create_data, f"JSON-RPC error or missing result: {create_data}"
    test_dir = os.path.join(DEV_ROOT, project_name)
    assert os.path.isdir(test_dir), f"Project directory not created: {test_dir}"
    return test_dir

def extract_shell_output(result):
    """Extracts string output from a shell result dict or string."""
    if isinstance(result, dict):
        content = result.get('content', result)
    else:
        content = result
    if isinstance(content, list):
        return "\n".join(item.get("text", str(item)) for item in content if isinstance(item, dict)).strip()
    return str(content).strip()

def get_last_non_empty_line(output):
    """Gets the last non-empty line from output."""
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ''

def mcp_execute_shell(server_url, command):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    shell_payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_EXECUTE_SHELL,
        "method": "tools/call",
        "params": {
            "name": "execute_shell",
            "arguments": {"command": command}
        }
    }
    shell_resp = requests.post(server_url, json=shell_payload, headers=headers)
    assert shell_resp.status_code == 200, f"Failed: {shell_resp.text}"
    shell_data = shell_resp.json()
    return extract_shell_output(shell_data["result"])

import getpass

def test_shell_echo_path(mcp_server):
    """Test echoing the $PATH environment variable."""
    project_name = 'pytest_combined_echo_path'
    project_dir = mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'echo "$PATH"')
    last_line = get_last_non_empty_line(shell_output)
    colon_count = last_line.count(":")
    # Assert $PATH line looks plausible: not empty and has at least one colon
    assert last_line, f"$PATH is empty: {last_line!r}"
    assert ':' in last_line, f"$PATH does not contain ':': {last_line!r}"

def test_shell_echo_user(mcp_server):
    """Test echoing the current user with 'whoami'."""
    project_name = "pytest_combined_echo_user"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'whoami')
    last_line = get_last_non_empty_line(shell_output)
    expected_user = getpass.getuser()
    assert last_line == expected_user, f"Expected user '{expected_user}', got: {last_line!r}"

def test_shell_detect_nix_shell(mcp_server):
    """Test detection of nix-shell environment, expect not inside nix-shell."""
    project_name = "pytest_combined_nixshell"
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
    assert "Not inside nix-shell" in last_line, f"Expected not inside nix-shell, got: {last_line!r}"

def test_get_active_project(mcp_server):
    """Test getting the active project via API."""
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
    assert resp.status_code == 200, f"Failed get_active_project: {resp.text}"
    result = resp.json()["result"]
    struct = result.get("structuredContent")
    if struct is not None:
        name = struct.get("name")
        path = struct.get("path")
    else:
        name = result.get("name")
        path = result.get("path")
    assert name == project_name, f"Active project name should be {project_name}, got: {name!r}"
    assert path and path.endswith(project_name), f"Path should end with {project_name}, got: {path!r}"

def test_change_active_project(mcp_server):
    """Test changing the active project and listing projects."""
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
    assert resp.status_code == 200, f"Failed to change active project: {resp.text}"
    result = resp.json()["result"]
    get_payload = {"jsonrpc": "2.0", "id": 31, "method": "tools/call", "params": {"name": "get_active_project"}}
    get_resp = requests.post(mcp_server, json=get_payload, headers=headers)
    assert get_resp.status_code == 200
    struct = get_resp.json()["result"].get("structuredContent")
    name = struct.get("name") if struct else None
    assert name == project_a, f"Expected active {project_a}, got {name!r}"
    # Verify shell $PWD matches
    echo_output = mcp_execute_shell(mcp_server, "echo $PWD")
    assert echo_output.endswith(f"{DEV_ROOT}/{project_a}"), f"Shell $PWD: got {echo_output!r}"
    # Create more projects and check list
    names = ["projA", "projB", "projC"]
    for n in names:
        mcp_create_project(mcp_server, n)
        assert os.path.isdir(os.path.join(DEV_ROOT, n)), f"Project directory not created for {n}"
    list_payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_LIST_PROJECTS,
        "method": "tools/call",
        "params": {"name": "list_all_projects"},
    }
    resp = requests.post(mcp_server, json=list_payload, headers=headers)
    assert resp.status_code == 200, f"Failed to list projects: {resp.text}"
    result = resp.json()["result"]
    if isinstance(result, dict) and "content" in result:
        project_names = [item.get("text") for item in result["content"] if isinstance(item, dict)]
    else:
        project_names = result
    assert set(names).issubset(set(project_names)), f"Expected at least {names} in projects: {project_names}"

def test_shell_double_pipe_or(mcp_server):
    """Test shell command with error/fallback using double pipe."""
    project_name = "pytest_shell_double_pipe_or"
    mcp_create_project(mcp_server, project_name)
    # Case 1: First command succeeds, second command ignored
    shell_output_1 = mcp_execute_shell(mcp_server, 'echo foo || echo bar')
    assert any("foo" in line for line in shell_output_1.splitlines()), f"Expected 'foo' when running 'echo foo || echo bar', got: {shell_output_1!r}"
    assert not any("bar" in line for line in shell_output_1.splitlines()), f"Unexpected 'bar' when first command succeeds: {shell_output_1!r}"
    # Case 2: First command fails, second command runs
    shell_output_2 = mcp_execute_shell(mcp_server, 'false || echo fallback')
    assert any("fallback" in line for line in shell_output_2.splitlines()), f"Expected 'fallback' when first command fails, got: {shell_output_2!r}"
    assert not any("foo" in line for line in shell_output_2.splitlines()), f"Unexpected 'foo' when first command fails: {shell_output_2!r}"

def test_shell_ls_or_echo(mcp_server):
    """Test 'ls' fallback to echo if directory missing."""
    project_name = "pytest_shell_ls_or_echo"
    mcp_create_project(mcp_server, project_name)
    cmd = 'ls -l /run/opengl-driver/lib/ 2>/dev/null || echo "Directory not found or empty"'
    shell_output = mcp_execute_shell(mcp_server, cmd)
    assert shell_output.strip(), "Shell output should not be empty."
    if "Directory not found or empty" in shell_output:
        assert shell_output.strip() == "Directory not found or empty", f"Fallback expected as only output, got: {shell_output!r}"
    else:
        # It should have a typical ls -l output header line (total N or drwx/ lrwx/ etc)
        assert any(l.strip().startswith(("d", "l", "-", "total")) for l in shell_output.splitlines()), f"Expected directory listing, got: {shell_output!r}"

