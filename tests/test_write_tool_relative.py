import os
import requests
import pytest

PORT = 8109
DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test-write")


@pytest.fixture(scope="module")
def mcp_server():
    import subprocess
    import shutil
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


def api_write_file(server_url, file_path, content, **extra_args):
    args = {"file_path": file_path, "content": content}
    args.update(extra_args)
    payload = {
        "jsonrpc": "2.0",
        "id": 8808,
        "method": "tools/call",
        "params": {
            "name": "write_file",
            "arguments": args,
        },
    }
    headers = {"Accept": "application/json"}
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"HTTP failure: {resp.text}"
    data = resp.json()
    assert "result" in data, f"No result: {data}"
    result = data["result"]
    if isinstance(result, dict):
        return result.get("structuredContent", {}).get("result") or result.get("content") or str(result)
    return str(result)


def api_read_file(server_url, file_path):
    payload = {
        "jsonrpc": "2.0",
        "id": 8809,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": {"file_path": file_path},
        },
    }
    headers = {"Accept": "application/json"}
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"HTTP failure: {resp.text}"
    data = resp.json()
    assert "result" in data, f"No result: {data}"
    result = data["result"]
    if isinstance(result, dict):
        if "structuredContent" in result and "result" in result["structuredContent"]:
            return result["structuredContent"]["result"]
        if "content" in result and isinstance(result["content"], list):
            return "\n".join(
                str(item.get("text", str(item))) for item in result["content"] if isinstance(item, dict)
            )
    return str(result)


def test_write_relative_path_in_project(mcp_server):
    """
    Test that writing to a relative path creates the file under the project root directory
    (as specified by the server's --projects-dir argument).
    """
    rel_dir = "relpath_dir"
    rel_file = "relfile.txt"
    rel_path = os.path.join(rel_dir, rel_file)
    server_url = mcp_server
    active_project_dir = os.path.join(DEV_ROOT, "default")
    abs_dir = os.path.join(active_project_dir, rel_dir)
    abs_file = os.path.join(abs_dir, rel_file)
    if os.path.exists(abs_file):
        os.remove(abs_file)
    if not os.path.exists(abs_dir):
        os.makedirs(abs_dir)
    test_content = "This is some test content."
    out = api_write_file(server_url, rel_path, test_content)
    print(f"Server write response: {out}")
    assert "Success" in out or "wrote" in out or "created" in out, f"Server output was: {out}"
    print(f"Checking if file exists at: {abs_file}")
    assert os.path.exists(abs_file), f"File wasn't created: {abs_file}"
    with open(abs_file, "r", encoding="utf-8") as f:
        filedata = f.read()
    assert filedata == test_content
    # Also verify reading through API (optional, if API supports relative read)
    result = api_read_file(server_url, rel_path)
    assert result == test_content or result.strip() == test_content
