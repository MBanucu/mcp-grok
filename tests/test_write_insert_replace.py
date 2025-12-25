from pathlib import Path
from tests.test_utils import api_write_file


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


def test_write_replace_start_at_zero(tmp_path, mcp_server):
    test_file = tmp_path / "replace-at-zero.txt"
    Path(test_file).write_text("a\nb\nc\nd\n")
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


def test_write_replace_fewer_lines_than_range(tmp_path, mcp_server):
    test_file = tmp_path / "replace-fewer.txt"
    Path(test_file).write_text("a\nb\nc\nd\ne\nf\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "X\n",
        replace_lines_start=1,
        replace_lines_end=5,
    )
    assert "replaced" in out or "Success" in out
    after = Path(test_file).read_text()
    assert after == "a\nX\nf\n"


def test_write_replace_more_lines_than_range(tmp_path, mcp_server):
    test_file = tmp_path / "replace-more.txt"
    Path(test_file).write_text("a\nb\nc\nd\ne\nf\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "L1\nL2\nL3\nL4\nL5\n",
        replace_lines_start=2,
        replace_lines_end=4,
    )
    assert "replaced" in out or "Success" in out
    after = Path(test_file).read_text()
    assert after == "a\nb\nL1\nL2\nL3\nL4\nL5\ne\nf\n"


def test_write_replace_lines_with_whitespace(tmp_path, mcp_server):
    test_file = tmp_path / "replace-lines-ws.txt"
    Path(test_file).write_text("a\nb\nc\nd\n")
    out = api_write_file(
        mcp_server,
        str(test_file),
        "   \n\n",
        replace_lines_start=1,
        replace_lines_end=3,
    )
    assert "replaced" in out
    after = Path(test_file).read_text()
    assert after == "a\n   \n\nd\n"
