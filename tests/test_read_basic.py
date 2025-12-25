from test_utils import api_read_file


def test_read_existing_file(tmp_path, mcp_server):
    test_file = tmp_path / "sample.txt"
    lines = [f"Line {i}" for i in range(30)]
    test_file.write_text("\n".join(lines))
    result = api_read_file(mcp_server, str(test_file))
    assert all(x in result for x in ("Line 0", "Line 29")), result
    result2 = api_read_file(mcp_server, str(test_file), limit=5)
    assert result2.strip().count("\n") <= 5
    assert "Line 5" not in result2
    result3 = api_read_file(mcp_server, str(test_file), limit=2, offset=10)
    assert "Line 10" in result3 and "Line 11" in result3
    assert "Line 9" not in result3


def test_read_nonexistent_file(mcp_server):
    result = api_read_file(mcp_server, "/tmp/this_file_does_not_exist_abcdefg.txt")
    assert "does not exist" in result


def test_read_binary_file(tmp_path, mcp_server):
    bf = tmp_path / "binfile.bin"
    bf.write_bytes(b"\x00abc\x00def")
    result = api_read_file(mcp_server, str(bf))
    assert "binary" in result or "Error" in result


def test_read_large_file(tmp_path, mcp_server):
    lf = tmp_path / "hugefile.txt"
    lf.write_bytes(b"X" * (10 * 1024 * 1024 + 1024))
    result = api_read_file(mcp_server, str(lf))
    assert "too large" in result


def test_read_directory(tmp_path, mcp_server):
    result = api_read_file(mcp_server, str(tmp_path))
    assert "not a file" in result or "does not exist" in result or "Error" in result


def test_read_init_py_file(tmp_path, mcp_server):
    init_file = tmp_path / "__init__.py"
    init_file.write_text("# init file\n")
    result = api_read_file(mcp_server, str(init_file))
    assert "# init file" in result or result.strip() == ""
