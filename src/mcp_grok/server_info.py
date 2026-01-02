import subprocess
from typing import TypedDict


class ServerInfoDict(TypedDict):
    pid: int
    port: int
    projects_dir: str
    logfile: str
    started_at: float
    audit_log: str


class ServerInfo:
    def __init__(
        self, pid: int, port: int, projects_dir: str, logfile: str,
        started_at: float, audit_log: str, proc: subprocess.Popen
    ):
        self.pid = pid
        self.port = port
        self.projects_dir = projects_dir
        self.logfile = logfile
        self.started_at = started_at
        self.audit_log = audit_log
        self.proc = proc

    def to_dict(self) -> ServerInfoDict:
        return ServerInfoDict(
            pid=self.pid,
            port=self.port,
            projects_dir=self.projects_dir,
            logfile=self.logfile,
            started_at=self.started_at,
            audit_log=self.audit_log,
        )