from pathlib import Path
from test_utils import api_write_file, api_read_file


def test_write_whole_file(tmp_path, mcp_server):
    test_file = tmp_path / "write_all.txt"
    server_url = mcp_server
    out = api_write_file(server_url, str(test_file), "hello\nworld\n")
    assert "Success" in out
    result = api_read_file(server_url, str(test_file))
    assert result.strip() == "hello\nworld"


def test_write_replaceall_full_file_overwrite(tmp_path, mcp_server):
    test_file = tmp_path / "replaceAll.txt"
    server_url = mcp_server
    Path(test_file).write_text("foo bar foo FOO Foo foo\n")
    out = api_write_file(server_url, str(test_file), "AAAAA", replaceAll=True)
    assert "Success" in out or "replaced" in out or "fully replaced" in out
    after = Path(test_file).read_text()
    assert after == "AAAAA"
    Path(test_file).write_text("BBBBB\nCCCCC\n")
    out2 = api_write_file(server_url, str(test_file), "ZZZZ", replaceAll=True)
    assert "Success" in out2 or "replaced" in out2 or "fully replaced" in out2
    after2 = Path(test_file).read_text()
    assert after2 == "ZZZZ"


def test_write_replaceall_nonexistent_file(tmp_path, mcp_server):
    test_file = tmp_path / "replaceAll-new.txt"
    server_url = mcp_server
    content = "Just created with replaceAll!"
    out = api_write_file(server_url, str(test_file), content, replaceAll=True)
    assert "Success" in out or "replaced" in out or "fully replaced" in out
    assert test_file.exists()
    after = test_file.read_text()
    assert after == content
