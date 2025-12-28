import os
import getpass
import dataclasses
from dataclasses import dataclass
from typing import List


import datetime

@dataclass
class Config:
    projects_dir: str = os.path.expanduser('~/dev/mcp-projects')
    shell_user: str = getpass.getuser()
    shell_cmd: List[str] = dataclasses.field(
        default_factory=lambda: [
            'sudo', '-u', getpass.getuser(), '--login', 'bash', '-l'
        ]
    )
    log_timestamp: str = dataclasses.field(default_factory=lambda: datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))

    @property
    def mcp_server_log(self):
        return os.path.expanduser(f'~/.mcp-grok/mcp_server_{self.log_timestamp}.log')

    @property
    def proxy_log(self):
        return os.path.expanduser(f'~/.mcp-grok/superassistant_proxy_{self.log_timestamp}.log')

    @property
    def server_audit_log(self):
        return os.path.expanduser(f'~/.mcp-grok/server_audit_{self.log_timestamp}.log')

    port: int = 8000
    default_project: str = 'default'
