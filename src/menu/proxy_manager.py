import subprocess
import os
from typing import Optional
from mcp_grok.config import config


def _writable_logfile(log_path):
    """Ensure the log file directory exists and return the path."""
    dir_path = os.path.dirname(log_path)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    return log_path


class ProxyManager:
    def __init__(self, config_path=None, port=3006):
        self.config_path = config_path
        self.port = port
        self.proc: Optional[subprocess.Popen[bytes]] = None

    def start_proxy(self) -> subprocess.Popen[bytes]:
        log = open(_writable_logfile(config.proxy_log), "a")
        cmd = ['superassistant-proxy', '--port', str(self.port)]
        if self.config_path:
            cmd.extend(['--config', self.config_path])
        self.proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            env={**os.environ, 'NO_COLOR': '1'},
        )
        return self.proc

    def stop_proxy(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(timeout=5)
