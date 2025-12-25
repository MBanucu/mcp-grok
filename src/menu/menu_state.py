import subprocess
from typing import Optional
from . import menu_core


class MenuState:
    """
    Holds current process state for MCP server and proxy process.
    """

    def __init__(self):
        self.mcp_proc: Optional[subprocess.Popen] = None
        self.proxy_proc: Optional[subprocess.Popen] = None

    def is_mcp_running(self) -> bool:
        return self.mcp_proc is not None and self.mcp_proc.poll() is None

    def is_proxy_running(self) -> bool:
        return self.proxy_proc is not None and self.proxy_proc.poll() is None

    def start_mcp(self):
        if not self.is_mcp_running():
            self.mcp_proc = menu_core.server_manager.start_server()

    def stop_mcp(self):
        menu_core.server_manager.stop_server()
        self.mcp_proc = None

    def start_proxy(self):
        if not self.is_proxy_running():
            self.proxy_proc = menu_core.start_proxy()

    def stop_proxy(self):
        menu_core.stop_proxy(self.proxy_proc)
        self.proxy_proc = None
