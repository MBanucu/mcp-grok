from test_utils import mcp_create_project, mcp_execute_shell


def test_shell_double_pipe_or(mcp_server):
    project_name = "pytest_shell_double_pipe_or"
    mcp_create_project(mcp_server, project_name)
    # Command succeeds
    out1 = mcp_execute_shell(mcp_server, 'echo foo || echo bar')
    assert any("foo" in line for line in out1.splitlines()), f"Expected 'foo', got: {out1!r}"
    assert not any("bar" in line for line in out1.splitlines()), f"Unexpected 'bar': {out1!r}"
    # Command fails
    out2 = mcp_execute_shell(mcp_server, 'false || echo fallback')
    assert any("fallback" in line for line in out2.splitlines()), f"Expected 'fallback', got: {out2!r}"
    assert not any("foo" in line for line in out2.splitlines()), f"Unexpected 'foo': {out2!r}"


def test_shell_ls_or_echo(mcp_server):
    project_name = "pytest_shell_ls_or_echo"
    mcp_create_project(mcp_server, project_name)
    cmd = 'ls -l /run/opengl-driver/lib/ 2>/dev/null || echo "Directory not found or empty"'
    shell_output = mcp_execute_shell(mcp_server, cmd)
    assert shell_output.strip(), "Shell output should not be empty."
    if "Directory not found or empty" in shell_output:
        assert shell_output.strip() == "Directory not found or empty", f"Fallback expected, got: {shell_output!r}"
    else:
        # Directory listing expected
        assert any(
            line.strip().startswith(("d", "l", "-", "total"))
            for line in shell_output.splitlines()
        ), f"Expected dir listing, got: {shell_output!r}"
