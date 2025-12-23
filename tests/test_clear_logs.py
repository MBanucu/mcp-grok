import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import menu_core

def test_clear_mcp_log():
    # Write something, then clear
    with open(menu_core.MCP_LOGFILE, 'w') as f:
        f.write('some text\n')
    menu_core.clear_log(menu_core.MCP_LOGFILE)
    with open(menu_core.MCP_LOGFILE, 'r') as f:
        assert f.read() == '', "MCP log not cleared"
    print("PASS: MCP Server log cleared.")

def test_clear_proxy_log():
    # Write something, then clear
    with open(menu_core.PROXY_LOGFILE, 'w') as f:
        f.write('other text\n')
    menu_core.clear_log(menu_core.PROXY_LOGFILE)
    with open(menu_core.PROXY_LOGFILE, 'r') as f:
        assert f.read() == '', "Proxy log not cleared"
    print("PASS: Proxy log cleared.")
