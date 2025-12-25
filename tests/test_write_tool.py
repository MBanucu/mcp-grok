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

# --- Main tests: overwrite, replace, insert, edge, delete ---


def test_write_whole_file(tmp_path, mcp_server):
    test_file = tmp_path / "write_all.txt"
    server_url = mcp_server
    out = api_write_file(server_url, str(test_file), "hello\nworld\n")
    assert "Success" in out
    result = api_read_file(server_url, str(test_file))
    assert result.strip() == "hello\nworld"


def test_write_replace_lines(tmp_path, mcp_server):
    test_file = tmp_path / "replace.txt"
    original = "zero\none\ntwo\nthree\nfour\n"
    Path(test_file).write_text(original)
    out = api_write_file(
        mcp_server,
        str(test_file),
        "ONE\nTWO\n",
        replace_lines_start=1,
        replace_lines_end=3,
    )
    assert "Success: Lines 1:3" in out
    after = Path(test_file).read_text()
    assert after == "zero\nONE\nTWO\nthree\nfour\n"


def test_write_insert_lines(tmp_path, mcp_server):
    test_file = tmp_path / "insert.txt"
    Path(test_file).write_text("a\nb\nd\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "c1\nc2\n",
        insert_at_line=2,
    )
    assert "Inserted at line 2" in out
    after = Path(test_file).read_text()
    assert after == "a\nb\nc1\nc2\nd\n"


def test_write_insert_at_end(tmp_path, mcp_server):
    test_file = tmp_path / "insert-end.txt"
    Path(test_file).write_text("a\nb\nc\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "d\ne\n",
        insert_at_line=10,
    )
    assert "Inserted at line 10" in out
    after = Path(test_file).read_text()
    assert after == "a\nb\nc\n\n\n\n\n\n\n\nd\ne\n"


def test_write_insert_and_replace_mutually_exclusive(tmp_path, mcp_server):
    test_file = tmp_path / "exclusive.txt"
    Path(test_file).write_text("one\ntwo\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "BAD\n",
        replace_lines_start=0,
        replace_lines_end=1,
        insert_at_line=1,
    )
    assert "Cannot specify both" in out or "Error" in out


def test_write_nonexistent_file_insert(tmp_path, mcp_server):
    test_file = tmp_path / "insert-new.txt"
    out = api_write_file(
        mcp_server,
        str(test_file),
        "foo\nbar\n",
        insert_at_line=0,
    )
    assert "Inserted at line 0" in out
    result = api_read_file(mcp_server, str(test_file))
    assert result.strip() == "foo\nbar"


def test_write_nonexistent_file_replace(tmp_path, mcp_server):
    test_file = tmp_path / "replace-new.txt"
    out = api_write_file(
        mcp_server,
        str(test_file),
        "foo\n",
        replace_lines_start=0,
        replace_lines_end=1,
    )
    assert "does not exist" in out or "error" in out.lower()


def test_write_negative_insert(tmp_path, mcp_server):
    test_file = tmp_path / "neg-insert.txt"
    Path(test_file).write_text("x\ny\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "FIRST\n",
        insert_at_line=-5,
    )
    assert "Inserted at line 0" in out
    after = Path(test_file).read_text()
    assert after.startswith("FIRST\n")


def test_write_invalid_range(tmp_path, mcp_server):
    test_file = tmp_path / "invalidrange.txt"
    Path(test_file).write_text("x\ny\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "F\n",
        replace_lines_start=2,
        replace_lines_end=1,
    )
    assert "Invalid line range" in out or "error" in out.lower()

# --- Replace from file start (start=0) ---


def test_write_replace_start_at_zero(tmp_path, mcp_server):
    test_file = tmp_path / "replace-at-zero.txt"
    Path(test_file).write_text("a\nb\nc\nd\n")
    # Replace lines 0 and 1 (first two lines)
    out = api_write_file(
        mcp_server,
        str(test_file),
        "X\nY\n",
        replace_lines_start=0,
        replace_lines_end=2,
    )
    assert "replaced" in out or "Success" in out
    after = Path(test_file).read_text()
    assert after == "X\nY\nc\nd\n"


# --- Replace with content length mismatch (expand/shrink) ---

def test_write_replace_fewer_lines_than_range(tmp_path, mcp_server):
    test_file = tmp_path / "replace-fewer.txt"
    Path(test_file).write_text("a\nb\nc\nd\ne\nf\n")
    # Replace lines 1:5 (4 lines) with ONE line
    out = api_write_file(
        mcp_server,
        str(test_file),
        "X\n",
        replace_lines_start=1,
        replace_lines_end=5,
    )
    assert "replaced" in out or "Success" in out
    after = Path(test_file).read_text()
    # a (then replace lines 1 to 4 with X), then f left
    assert after == "a\nX\nf\n"


def test_write_replace_more_lines_than_range(tmp_path, mcp_server):
    test_file = tmp_path / "replace-more.txt"
    Path(test_file).write_text("a\nb\nc\nd\ne\nf\n")
    # Replace 2:4 (c, d) with FIVE lines
    out = api_write_file(
        mcp_server,
        str(test_file),
        "L1\nL2\nL3\nL4\nL5\n",
        replace_lines_start=2,
        replace_lines_end=4,
    )
    assert "replaced" in out or "Success" in out
    after = Path(test_file).read_text()
    # a b (replace c, d with 5 lines), then e f left
    assert after == "a\nb\nL1\nL2\nL3\nL4\nL5\ne\nf\n"


# --- Delete lines tests ---

def test_write_delete_lines(tmp_path, mcp_server):
    test_file = tmp_path / "delete-lines.txt"
    Path(test_file).write_text("one\ntwo\nthree\nfour\nfive\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "",
        replace_lines_start=1,
        replace_lines_end=3,
    )
    assert "Deleted" in out
    after = Path(test_file).read_text()
    assert after == "one\nfour\nfive\n"


def test_write_replace_lines_with_whitespace(tmp_path, mcp_server):
    test_file = tmp_path / "replace-lines-ws.txt"
    Path(test_file).write_text("a\nb\nc\nd\n")
    # Content is whitespace: should REPLACE lines 1:3 (b, c) with exactly the provided string
    out = api_write_file(
        mcp_server,
        str(test_file),
        "   \n\n",
        replace_lines_start=1,
        replace_lines_end=3,
    )
    assert "replaced" in out
    after = Path(test_file).read_text()
    # '   \n\n' splits to two lines: a line of spaces and a blank line
    assert after == "a\n   \n\nd\n"


def test_write_delete_beyond_eof(tmp_path, mcp_server):
    test_file = tmp_path / "delete-beyond.txt"
    Path(test_file).write_text("1\n2\n3\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "",
        replace_lines_start=2,
        replace_lines_end=10,
    )
    assert "Deleted" in out
    after = Path(test_file).read_text()
    assert after == "1\n2\n"


def test_write_delete_entire_file(tmp_path, mcp_server):
    test_file = tmp_path / "delete-entire.txt"
    Path(test_file).write_text("aa\nbb\ncc\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "",
        replace_lines_start=0,
        replace_lines_end=100,
    )
    assert "Deleted" in out
    after = Path(test_file).read_text()
    assert after == ""


def test_write_replaceall_full_file_overwrite(tmp_path, mcp_server):
    test_file = tmp_path / "replaceAll.txt"
    Path(test_file).write_text("foo bar foo FOO Foo foo\n")
    server_url = mcp_server
    # replaceAll should fully overwrite the file with given content
    out = api_write_file(server_url, str(test_file), "AAAAA", replaceAll=True)
    assert "Success" in out or "replaced" in out or "fully replaced" in out
    after = Path(test_file).read_text()
    assert after == "AAAAA"
    # Write different file, confirm again
    Path(test_file).write_text("BBBBB\nCCCCC\n")
    out2 = api_write_file(server_url, str(test_file), "ZZZZ", replaceAll=True)
    assert "Success" in out2 or "replaced" in out2 or "fully replaced" in out2
    after2 = Path(test_file).read_text()
    assert after2 == "ZZZZ"
