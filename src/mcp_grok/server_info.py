import subprocess
from typing import TypedDict


class ServerInfoDict(TypedDict):
    pid: int
    port: int
    projects_dir: str
    logfile: str
    started_at: float
    audit_log: str


class ProxyInfoDict(TypedDict):
    pid: int
    port: int
    logfile: str
    started_at: float


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


class ProxyInfo:
    def __init__(
        self, pid: int, port: int, logfile: str,
        started_at: float, proc: subprocess.Popen, proxy_manager, config_path=None
    ):
        self.pid = pid
        self.port = port
        self.logfile = logfile
        self.started_at = started_at
        self.proc = proc
        self.proxy_manager = proxy_manager
        self.config_path = config_path

    def to_dict(self) -> ProxyInfoDict:
        return ProxyInfoDict(
            pid=self.pid,
            port=self.port,
            logfile=self.logfile,
            started_at=self.started_at,
        )
