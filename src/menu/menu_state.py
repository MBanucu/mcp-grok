import subprocess
import sys
import time
from typing import Optional
from . import menu_core
from mcp_grok import server_client
from mcp_grok.config import config


class MenuState:
    """
    Holds current process state for MCP server and proxy process.
    """

    def __init__(self):
        self.mcp_running: bool = False
        self.proxy_proc: Optional[subprocess.Popen] = None
        # Check if daemon is already running
        try:
            server_client.list_servers()
            # Daemon is running
            pass
        except Exception:
            # Start daemon as subprocess
            subprocess.Popen([
                sys.executable, '-m', 'mcp_grok.server_daemon'
            ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Wait for daemon to be ready
            for _ in range(30):  # 3 seconds
                try:
                    server_client.list_servers()
                    break
                except Exception:
                    time.sleep(0.1)
            else:
                raise RuntimeError("Daemon did not start in time")

    def is_mcp_running(self) -> bool:
        try:
            servers = server_client.list_servers()
            return len(servers.get("servers", {})) > 0
        except Exception:
            return False

    def start_mcp(self):
        if not self.is_mcp_running():
            try:
                server_client.start_server(port=config.port, projects_dir=config.projects_dir)
                self.mcp_running = True
            except Exception as e:
                print(f"Failed to start server via daemon: {e}")
                self.mcp_running = False

    def stop_mcp(self):
        try:
            servers = server_client.list_servers()
            for pid_str in servers.get("servers", {}):
                server_client.stop_managed_server(pid=int(pid_str))
        except Exception as e:
            print(f"Failed to stop servers via daemon: {e}")
        self.mcp_running = False

    def is_proxy_running(self) -> bool:
        return self.proxy_proc is not None and self.proxy_proc.poll() is None

    def start_proxy(self):
        if not self.is_proxy_running():
            self.proxy_proc = menu_core.start_proxy()

    def stop_proxy(self):
        menu_core.stop_proxy(self.proxy_proc)
        self.proxy_proc = None

    def stop_daemon(self):
        try:
            server_client.stop_daemon()
        except Exception:
            pass
