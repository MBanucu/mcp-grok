from pathlib import Path
from test_utils import api_write_file, api_read_file


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
