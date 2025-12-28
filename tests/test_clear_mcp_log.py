import pytest
from menu import menu_core
from mcp_grok.config import config

def test_clear_mcp_log():
    # Write something, then clear
    with open(config.mcp_shell_log, 'w') as f:
        f.write('some text\n')
    menu_core.clear_log(config.mcp_shell_log)
    with open(config.mcp_shell_log, 'r') as f:
        assert f.read() == '', "MCP log not cleared"
