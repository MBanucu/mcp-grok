import os
import getpass
import dataclasses
from dataclasses import dataclass
from typing import List, Optional

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
    audit_log: Optional[str] = None
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
    def mcp_shell_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{self.log_timestamp}_{self.port}_mcp-shell.log')

    @property
    def proxy_log(self):
        return os.path.expanduser(f'~/.mcp-grok/{self.log_timestamp}_{self.port}_proxy.log')

    @property
    def server_audit_log(self):
        if self.audit_log:
            return self.audit_log
        return os.path.expanduser(f'~/.mcp-grok/{self.log_timestamp}_{self.port}_audit.log')


# The canonical singleton Config instance for codebase-wide import
config = Config()
