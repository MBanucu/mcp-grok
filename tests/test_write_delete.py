from pathlib import Path
from tests.test_utils import api_write_file


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
