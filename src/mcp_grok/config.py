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
    port: int = 8000
    default_project: str = 'default'
    log_timestamp: str = dataclasses.field(init=False)

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
        return cls._instance

    def __post_init__(self):
        if not hasattr(self, 'log_timestamp'):
            self.log_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    @property
    def mcp_server_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{self.log_timestamp}_mcp_server.log')

    @property
    def proxy_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{self.log_timestamp}_superassistant_proxy.log')

    @property
    def server_audit_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{self.log_timestamp}_server_audit.log')

# The canonical singleton Config instance for codebase-wide import
config = Config()
