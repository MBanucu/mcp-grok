import os
import subprocess
import time
import shutil
import requests
import select
import pytest

PORT = 8099
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
        "python", "server.py", "--port", str(PORT), "--projects-dir", DEV_ROOT],
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

def mcp_execute_shell(server_url, command):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    shell_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "execute_shell",
            "arguments": {"command": command}
        }
    }
    shell_resp = requests.post(server_url, json=shell_payload, headers=headers)
    assert shell_resp.status_code == 200, f"Failed: {shell_resp.text}"
    shell_data = shell_resp.json()
    content = shell_data["result"].get("content", []) if isinstance(shell_data["result"], dict) else shell_data["result"]
    if isinstance(content, list):
        shell_output = "\n".join(item.get("text", str(item)) for item in content if isinstance(item, dict)).strip()
    else:
        shell_output = str(content).strip()
    return shell_output

def test_shell_echo_path(mcp_server):
    project_name = "pytest_combined_echo_path"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'echo "$PATH"')
    print(f"SHELL OUTPUT FOR ECHO PATH:\n{shell_output}\n--- END SHELL OUTPUT ---")
    last_line = [line for line in shell_output.splitlines() if line.strip()][-1]
    colon_count = last_line.count(":")
    assert 1 <= colon_count <= 6, f"$PATH has {colon_count} ':'s, expected at most 6: {last_line!r}"
    assert "michi" in last_line, f"$PATH did not contain 'michi': {last_line!r}"

def test_shell_echo_user(mcp_server):
    project_name = "pytest_combined_echo_user"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'whoami')
    print(f"SHELL OUTPUT FOR WHOAMI:\n{shell_output}\n--- END SHELL OUTPUT ---")
    last_line = [line for line in shell_output.splitlines() if line.strip()][-1]
    assert last_line == "michi", f"Expected user 'michi', got: {last_line!r}"

def test_shell_detect_nix_shell(mcp_server):
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
    print(f"SHELL OUTPUT FOR NIX-SHELL DETECT:\n{shell_output}\n--- END SHELL OUTPUT ---")
    last_line = [line for line in shell_output.splitlines() if line.strip()][-1]
    assert "Not inside nix-shell" in last_line, f"Expected not inside nix-shell, got: {last_line!r}"

def test_get_active_project(mcp_server):
    project_name = "proj_active_test"
    mcp_create_project(mcp_server, project_name)
    # Call get_active_project
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 18,
        "method": "tools/call",
        "params": {"name": "get_active_project"},
    }
    resp = requests.post(mcp_server, json=payload, headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    result = resp.json()["result"]
    print(f"RAW get_active_project RESPONSE: {resp.json()}")
    # FastMCP returns Pydantic result inside 'structuredContent' for BaseModel
    struct = result.get("structuredContent")
    if struct is not None:
        name = struct.get("name")
        path = struct.get("path")
    else:
        name = result.get("name")
        path = result.get("path")
    print(f"Active project name: {name}, path: {path}")
    assert name == project_name, f"Active project name should be {project_name}, got: {name!r}"
    assert path and path.endswith(project_name), f"Path should end with {project_name}, got: {path!r}"

def test_change_active_project(mcp_server):
    project_a = "projA"
    project_b = "projB"
    mcp_create_project(mcp_server, project_a)
    mcp_create_project(mcp_server, project_b)
    # Change active project to A
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    change_payload = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {"name": "change_active_project", "arguments": {"project_name": project_a}},
    }
    resp = requests.post(mcp_server, json=change_payload, headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    result = resp.json()["result"]
    # Now get active project
    get_payload = {"jsonrpc": "2.0", "id": 31, "method": "tools/call", "params": {"name": "get_active_project"}}
    get_resp = requests.post(mcp_server, json=get_payload, headers=headers)
    assert get_resp.status_code == 200
    struct = get_resp.json()["result"].get("structuredContent")
    name = struct.get("name") if struct else None
    assert name == project_a, f"Expected active {project_a}, got {name!r}"

    # Also verify shell PWD matches
    echo_payload = {
        "jsonrpc": "2.0",
        "id": 32,
        "method": "tools/call",
        "params": {"name": "execute_shell", "arguments": {"command": "echo $PWD"}},
    }
    echo_resp = requests.post(mcp_server, json=echo_payload, headers=headers)
    assert echo_resp.status_code == 200
    echo_result = echo_resp.json()["result"]
    content = echo_result.get("content")
    if isinstance(content, list):
        echo_output = "\n".join(item.get("text", str(item)) for item in content if isinstance(item, dict)).strip()
    else:
        echo_output = str(content).strip() if content else str(echo_result).strip()
    assert echo_output.endswith(f"{DEV_ROOT}/{project_a}"), f"Shell $PWD: got {echo_output!r}"

    names = ["projA", "projB", "projC"]
    for n in names:
        mcp_create_project(mcp_server, n)
        assert os.path.isdir(os.path.join(DEV_ROOT, n))
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    list_payload = {
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {"name": "list_all_projects"},
    }
    resp = requests.post(mcp_server, json=list_payload, headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    result = resp.json()["result"]
    if isinstance(result, dict) and "content" in result:
        project_names = [item.get("text") for item in result["content"] if isinstance(item, dict)]
    else:
        project_names = result
    print(f"Projects listed: {project_names}")
    assert set(names).issubset(set(project_names)), f"Expected at least {names} in projects: {project_names}"

def test_shell_exit_and_reuse(mcp_server):
    project_name = "pytest_combined_exit_reuse"
    mcp_create_project(mcp_server, project_name)
    # Exit persistent shell
    exit_output = mcp_execute_shell(mcp_server, 'exit')
    print(f"SHELL EXIT OUTPUT:\n{exit_output}\n--- END SHELL EXIT OUTPUT ---")
    # Try echo $PATH again (should error)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "execute_shell",
            "arguments": {"command": "echo $PATH"}
        }
    }
    echo_resp = requests.post(mcp_server, json=payload, headers=headers)
    assert echo_resp.status_code == 200, f"Failed: {echo_resp.text}"
    echo_data = echo_resp.json()
    content = echo_data["result"].get("content", []) if isinstance(echo_data["result"], dict) else echo_data["result"]
    if isinstance(content, list):
        echo_output = "\n".join(item.get("text", str(item)) for item in content if isinstance(item, dict)).strip()
    else:
        echo_output = str(content).strip()
    print(f"SHELL OUTPUT FOR ECHO PATH AFTER EXIT:\n{echo_output}\n--- END SHELL OUTPUT ---")
    assert "Session shell not running" in echo_output or "Please create a project first" in echo_output or "Error" in echo_output, f"Unexpected PATH-after-exit: {echo_output!r}"

def test_shell_double_pipe_or(mcp_server):
    project_name = "pytest_shell_double_pipe_or"
    mcp_create_project(mcp_server, project_name)

    # Case 1: First command succeeds, second ignored
    shell_output_1 = mcp_execute_shell(mcp_server, 'echo foo || echo bar')
    print(f"SHELL OUTPUT FOR 'echo foo || echo bar':\n{shell_output_1}\n--- END SHELL OUTPUT ---")
    # Should contain only 'foo' if shell works correctly
    assert any("foo" in line for line in shell_output_1.splitlines()), f"Expected 'foo' when running 'echo foo || echo bar', got: {shell_output_1!r}"
    assert not any("bar" in line for line in shell_output_1.splitlines()), f"Unexpected 'bar' when first command succeeds: {shell_output_1!r}"

    # Case 2: First command fails, second runs
    shell_output_2 = mcp_execute_shell(mcp_server, 'false || echo fallback')
    print(f"SHELL OUTPUT FOR 'false || echo fallback':\n{shell_output_2}\n--- END SHELL OUTPUT ---")
    # Should contain only 'fallback'
    assert any("fallback" in line for line in shell_output_2.splitlines()), f"Expected 'fallback' when first command fails, got: {shell_output_2!r}"
    assert not any("foo" in line for line in shell_output_2.splitlines()), f"Unexpected 'foo' when first command fails: {shell_output_2!r}"

def test_shell_ls_or_echo(mcp_server):
    project_name = "pytest_shell_ls_or_echo"
    mcp_create_project(mcp_server, project_name)
    cmd = 'ls -l /run/opengl-driver/lib/ 2>/dev/null || echo "Directory not found or empty"'
    shell_output = mcp_execute_shell(mcp_server, cmd)
    print(f"SHELL OUTPUT FOR `{cmd}`:\n{shell_output}\n--- END SHELL OUTPUT ---")
    # It should either list contents, or echo fallback
    assert shell_output.strip(), "Shell output should not be empty."
    if "Directory not found or empty" in shell_output:
        assert shell_output.strip() == "Directory not found or empty", f"Fallback expected as only output, got: {shell_output!r}"
    else:
        # It should have a typical ls -l output header line (total N or drwx/ lrwx/ etc)
        assert any(l.strip().startswith(("d", "l", "-", "total")) for l in shell_output.splitlines()), f"Expected directory listing, got: {shell_output!r}"

