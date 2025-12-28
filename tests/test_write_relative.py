import os
from tests.test_utils import api_write_file, api_read_file


from tests.test_utils import api_change_active_project

def test_write_relative_path_in_project(mcp_server):
    server_url = mcp_server
    api_change_active_project(server_url, "default")
    rel_dir = "relpath_dir"
    rel_file = "relfile.txt"
    rel_path = os.path.join(rel_dir, rel_file)
    DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")
    active_project_dir = os.path.join(DEV_ROOT, "default")
    abs_dir = os.path.join(active_project_dir, rel_dir)
    abs_file = os.path.join(abs_dir, rel_file)
    if os.path.exists(abs_file):
        os.remove(abs_file)
    if not os.path.exists(abs_dir):
        os.makedirs(abs_dir)
    test_content = "This is some test content."
    out = api_write_file(server_url, rel_path, test_content)
    assert "Success" in out or "wrote" in out or "created" in out, f"Server output was: {out}"
    assert os.path.exists(abs_file), f"File wasn't created: {abs_file}"
    with open(abs_file, "r", encoding="utf-8") as f:
        filedata = f.read()
    assert filedata == test_content
    # Also verify reading through API (optional, if API supports relative read)
    result = api_read_file(server_url, rel_path)
    assert result == test_content or result.strip() == test_content
