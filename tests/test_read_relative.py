import os
from tests.test_utils import api_read_file


from tests.test_utils import api_change_active_project

def test_read_relative_path_in_project(mcp_server):
    server_url = mcp_server
    api_change_active_project(server_url, "default")
    rel_dir = "readdir_dir"
    rel_file = "readdata.txt"
    rel_path = os.path.join(rel_dir, rel_file)
    DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")
    active_project_dir = os.path.join(DEV_ROOT, "default")
    abs_dir = os.path.join(active_project_dir, rel_dir)
    abs_file = os.path.join(abs_dir, rel_file)
    if os.path.exists(abs_file):
        os.remove(abs_file)
    if not os.path.exists(abs_dir):
        os.makedirs(abs_dir)
    test_content = "Read tool project CWD relative test."
    with open(abs_file, "w", encoding="utf-8") as f:
        f.write(test_content)
    result = api_read_file(server_url, rel_path)
    assert result == test_content or result.strip() == test_content, f"API returned: {result!r} (expected: {test_content!r})"
