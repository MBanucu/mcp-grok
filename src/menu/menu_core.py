import os
import subprocess

from mcp_grok.config import config


def _writable_logfile(preferred):
    logdir = os.path.dirname(preferred)
    try:
        os.makedirs(logdir, exist_ok=True)
        with open(preferred, "a"):
            pass
        return preferred
    except Exception:
        fallback = "/tmp/" + os.path.basename(preferred)
        try:
            with open(fallback, "a"):
                pass
            return fallback
        except Exception:
            raise RuntimeError(f"Unable to create log file in {preferred} or /tmp")


class ProxyManager:
    def __init__(self):
        self.proc = None

    def start_proxy(self, config_path=None, port=3006):
        log = open(_writable_logfile(config.proxy_log), "a")
        cmd = ['superassistant-proxy', '--port', str(port)]
        if config_path:
            cmd.extend(['--config', config_path])
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


_proxy_manager = ProxyManager()


def start_proxy(config_path=None, port=3006):
    return _proxy_manager.start_proxy(config_path, port)


def stop_proxy(proc):
    _proxy_manager.stop_proxy()


def clear_log(log_path):
    if os.path.exists(log_path):
        with open(log_path, "w"):
            pass


def log_content(log_path):
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return f.read()
    return None
