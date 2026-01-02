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
    @staticmethod
    def start_proxy(config_path=None, port=3006):
        log = open(_writable_logfile(config.proxy_log), "a")
        cmd = ['superassistant-proxy', '--port', str(port)]
        if config_path:
            cmd.extend(['--config', config_path])
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            close_fds=True,
            env={**os.environ, 'NO_COLOR': '1'},
        )
        return proc

    @staticmethod
    def stop_proxy(proc):
        if proc and proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=5)


def start_proxy(config_path=None, port=3006):
    return ProxyManager.start_proxy(config_path, port)


def stop_proxy(proc):
    ProxyManager.stop_proxy(proc)


def clear_log(log_path):
    if os.path.exists(log_path):
        with open(log_path, "w"):
            pass


def log_content(log_path):
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return f.read()
    return None
