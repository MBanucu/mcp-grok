import os
from .proxy_manager import ProxyManager


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


def start_proxy(config_path=None, port=3006):
    manager = ProxyManager(config_path, port)
    manager.start_proxy()
    return manager


def clear_log(log_path):
    if os.path.exists(log_path):
        with open(log_path, "w"):
            pass


def log_content(log_path):
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return f.read()
    return None
