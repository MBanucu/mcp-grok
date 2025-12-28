import os
import getpass
import dataclasses
from dataclasses import dataclass
from typing import List


import datetime

# Module-level timestamp for all Config instances (one per process)
_LOG_TIMESTAMP = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

@dataclass
class Config:
    projects_dir: str = os.path.expanduser('~/dev/mcp-projects')
    shell_user: str = getpass.getuser()
    shell_cmd: List[str] = dataclasses.field(
        default_factory=lambda: [
            'sudo', '-u', getpass.getuser(), '--login', 'bash', '-l'
        ]
    )

    @property
    def mcp_server_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{_LOG_TIMESTAMP}_mcp_server.log')

    @property
    def proxy_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{_LOG_TIMESTAMP}_superassistant_proxy.log')

    @property
    def server_audit_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{_LOG_TIMESTAMP}_server_audit.log')

    port: int = 8000
    default_project: str = 'default'
