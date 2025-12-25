from tests.test_utils import api_read_file


def test_negative_offset_limit(tmp_path, mcp_server):
    tf = tmp_path / "weird.txt"
    tf.write_text("A\nB\nC\nD\nE")
    result = api_read_file(mcp_server, str(tf), limit=0)
    assert result.strip().startswith("A")
    result2 = api_read_file(mcp_server, str(tf), offset=-5)
    assert "A" in result2
    result3 = api_read_file(mcp_server, str(tf), offset=500)
    assert result3.strip() == ""
