import os
import requests
import pytest

PORT = 8099
RPC_ID_READ_FILE = 2001
USER_HOME = os.path.expanduser("~")
DEV_ROOT = os.path.join(USER_HOME, "dev", "mcp-projects-test")


@pytest.fixture(scope="module")
def mcp_server():
    import subprocess
    import shutil
    import time
    # Clean up dev root
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)
    os.makedirs(DEV_ROOT, exist_ok=True)
    server_proc = subprocess.Popen([
        "uv", "run", "python", "-m", "server", "--port", str(PORT), "--projects-dir", DEV_ROOT
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    # Wait for the server to become ready
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


def api_read_file(server_url, file_path, limit=None, offset=None):
    args = {"file_path": file_path}
    if limit is not None:
        args["limit"] = limit
    if offset is not None:
        args["offset"] = offset
    payload = {
        "jsonrpc": "2.0",
        "id": RPC_ID_READ_FILE,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": args,
        },
    }
    headers = {"Accept": "application/json"}
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"HTTP failure: {resp.text}"
    data = resp.json()
    assert "result" in data, f"No result: {data}"
    result = data["result"]
    # Try to extract main string content as returned by FastMCP
    if isinstance(result, dict):
        if "structuredContent" in result and "result" in result["structuredContent"]:
            return result["structuredContent"]["result"]
        if "content" in result and isinstance(result["content"], list):
            # Most likely [{"text": ...}]
            joined = "\n".join(
                str(item.get("text", str(item))) for item in result["content"] if isinstance(item, dict)
            )
            return joined
    return str(result)


def test_read_existing_file(tmp_path, mcp_server):
    # Create a test text file
    d = tmp_path
    test_file = d / "sample.txt"
    lines = [f"Line {i}" for i in range(30)]
    test_file.write_text("\n".join(lines))
    # Read the file (by absolute path)
    result = api_read_file(mcp_server, str(test_file))
    assert all(x in result for x in ("Line 0", "Line 29")), result
    # Read with limit
    result2 = api_read_file(mcp_server, str(test_file), limit=5)
    assert result2.strip().count("\n") <= 5
    assert "Line 5" not in result2
    # Read with offset
    result3 = api_read_file(mcp_server, str(test_file), limit=2, offset=10)
    assert "Line 10" in result3 and "Line 11" in result3
    assert "Line 9" not in result3


def test_read_nonexistent_file(mcp_server):
    result = api_read_file(mcp_server, "/tmp/this_file_does_not_exist_abcdefg.txt")
    assert "does not exist" in result


def test_read_binary_file(tmp_path, mcp_server):
    # Create a binary file
    bf = tmp_path / "binfile.bin"
    bf.write_bytes(b"\x00abc\x00def")
    result = api_read_file(mcp_server, str(bf))
    assert "binary" in result or "Error" in result


def test_read_large_file(tmp_path, mcp_server):
    # Create a large file (over 10MB)
    lf = tmp_path / "hugefile.txt"
    lf.write_bytes(b"X" * (10 * 1024 * 1024 + 1024))  # 10MB + 1KB
    result = api_read_file(mcp_server, str(lf))
    assert "too large" in result


def test_read_directory(tmp_path, mcp_server):
    result = api_read_file(mcp_server, str(tmp_path))
    assert "not a file" in result or "does not exist" in result or "Error" in result


def test_negative_offset_limit(tmp_path, mcp_server):
    tf = tmp_path / "weird.txt"
    tf.write_text("A\nB\nC\nD\nE")
    # limit=0
    result = api_read_file(mcp_server, str(tf), limit=0)
    assert result.strip().startswith("A")
    # negative offset
    result2 = api_read_file(mcp_server, str(tf), offset=-5)
    assert "A" in result2
    # offset past EOF
    result3 = api_read_file(mcp_server, str(tf), offset=500)
    assert result3.strip() == ""


def test_read_init_py_file(tmp_path, mcp_server):
    # Create a __init__.py file (matching real Python usage)
    init_file = tmp_path / "__init__.py"
    init_file.write_text("# init file\n")
    # Read with the MCP tool
    result = api_read_file(mcp_server, str(init_file))
    assert "# init file" in result or result.strip() == ""
