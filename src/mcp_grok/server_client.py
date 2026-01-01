"""Client for controlling the mcp-grok server daemon.

Provides simple HTTP calls to start/stop/list servers managed by the daemon.
"""
import json
import urllib.request
import urllib.error
from typing import Optional, Any

DEFAULT_DAEMON_PORT = 54000


class DaemonError(RuntimeError):
    pass


def _post(path: str, data: dict, daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    url = f"http://127.0.0.1:{daemon_port}{path}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode()
            raise DaemonError(f"Daemon error {e.code}: {body}")
        except Exception:
            raise DaemonError(f"Daemon HTTP error: {e}")
    except Exception as e:
        raise DaemonError(f"Failed to connect to daemon: {e}")


def _get(path: str, daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    url = f"http://127.0.0.1:{daemon_port}{path}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp)
    except Exception as e:
        raise DaemonError(f"Failed to connect to daemon: {e}")


def start_server(port: int, projects_dir: Optional[str] = None, daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    payload: dict[str, Any] = {"port": port}
    if projects_dir is not None:
        payload["projects_dir"] = projects_dir
    return _post("/start", payload, daemon_port=daemon_port)


def list_servers(daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    return _get("/list", daemon_port=daemon_port)


def stop_all(daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    return _post("/stop_all", {}, daemon_port=daemon_port)


# New clearer names (Option A)
def stop_daemon(daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    """Request the daemon process to stop itself."""
    return _post("/daemon/stop", {}, daemon_port=daemon_port)


def stop_managed_server(pid: Optional[int] = None, port: Optional[int] = None, daemon_port: int = DEFAULT_DAEMON_PORT) -> dict:
    """Stop a single managed server by pid or port."""
    payload: dict[str, Any] = {}
    if pid is not None:
        payload["pid"] = pid
    if port is not None:
        payload["port"] = port
    return _post("/server/stop", payload, daemon_port=daemon_port)
