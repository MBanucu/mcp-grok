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
    log_file: str = 'server_audit.log'
    port: int = 8000
    default_project: str = 'default'
