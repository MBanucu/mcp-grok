import os
import requests
import pytest
from pathlib import Path

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

def test_write_replaceall_nonexistent_file(tmp_path, mcp_server):
    test_file = tmp_path / "replaceAll-new.txt"
    server_url = mcp_server
    # This file does NOT exist before operation
    content = "Just created with replaceAll!"
    out = api_write_file(server_url, str(test_file), content, replaceAll=True)
    assert "Success" in out or "replaced" in out or "fully replaced" in out
    assert test_file.exists()
    after = test_file.read_text()
    assert after == content
