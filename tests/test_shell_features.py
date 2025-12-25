import getpass
from test_utils import mcp_create_project, mcp_execute_shell, get_last_non_empty_line

def test_shell_echo_path(mcp_server):
    project_name = "pytest_echo_path"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'echo "$PATH"')
    last_line = get_last_non_empty_line(shell_output)
    assert last_line, f"$PATH empty: {last_line!r}"
    assert ':' in last_line, f"$PATH missing ':': {last_line!r}"

def test_shell_echo_user(mcp_server):
    project_name = "pytest_echo_user"
    mcp_create_project(mcp_server, project_name)
    shell_output = mcp_execute_shell(mcp_server, 'whoami')
    last_line = get_last_non_empty_line(shell_output)
    expected_user = getpass.getuser()
    assert last_line == expected_user, f"User mismatch: expected {expected_user}, got {last_line!r}"

def test_shell_detect_nix_shell(mcp_server):
    project_name = "pytest_nixshell"
    mcp_create_project(mcp_server, project_name)
    shell_script = '''
    if [[ -n "$IN_NIX_SHELL" ]]; then
        echo "Inside nix-shell ($IN_NIX_SHELL)"
    else
        echo "Not inside nix-shell"
    fi
    '''.strip()
    shell_output = mcp_execute_shell(mcp_server, shell_script)
    last_line = get_last_non_empty_line(shell_output)
    assert "Not inside nix-shell" in last_line, f"Expected outside nix-shell, got: {last_line!r}"
