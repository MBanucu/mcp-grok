import os
from menu import menu_core
from mcp_grok.config import config

def test_clear_proxy_log():
    # Write something, then clear
    with open(config.proxy_log, 'w') as f:
        f.write('other text\n')
    menu_core.clear_log(config.proxy_log)
    with open(config.proxy_log, 'r') as f:
        assert f.read() == '', "Proxy log not cleared"
