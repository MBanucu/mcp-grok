import os
import getpass
import dataclasses
from dataclasses import dataclass
from typing import List


@dataclass
class Config:
    projects_dir: str = os.path.expanduser('~/dev/mcp-projects')
    shell_user: str = getpass.getuser()
    shell_cmd: List[str] = dataclasses.field(
        default_factory=lambda: [
            'sudo', '-u', getpass.getuser(), '--login', 'bash', '-l'
        ]
    )
    # Centralized log files
    mcp_server_log: str = os.path.expanduser('~/.mcp-grok/mcp_server.log')
    proxy_log: str = os.path.expanduser('~/.mcp-grok/superassistant_proxy.log')
    server_audit_log: str = os.path.expanduser('~/.mcp-grok/server_audit.log')
    port: int = 8000
    default_project: str = 'default'
