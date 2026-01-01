"""Minimal server daemon for managing mcp-grok-server subprocesses.

This is a PoC HTTP daemon that listens on localhost and provides JSON
endpoints for starting, stopping, listing and stopping-all managed servers.

Intended for use by tests via `server_client.py`.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import os
import subprocess
import signal
import time
from typing import Dict, Any, Optional, TypedDict

from .server_client import DEFAULT_DAEMON_PORT
from .config import config


class ServerInfoDict(TypedDict):
    pid: int
    port: int
    projects_dir: str
    logfile: str
    started_at: float

class ServerInfo:
    def __init__(self, pid: int, port: int, projects_dir: str, logfile: str, started_at: float, proc: subprocess.Popen):
        self.pid = pid
        self.port = port
        self.projects_dir = projects_dir
        self.logfile = logfile
        self.started_at = started_at
        self.proc = proc
    def to_dict(self) -> ServerInfoDict:
        return ServerInfoDict(
            pid=self.pid,
            port=self.port,
            projects_dir=self.projects_dir,
            logfile=self.logfile,
            started_at=self.started_at,
        )

HOST = "127.0.0.1"
DAEMON_PORT = DEFAULT_DAEMON_PORT

_SERVERS_LOCK = threading.Lock()
# pid -> info dict {pid, port, projects_dir, logfile, started_at}
_SERVERS: Dict[int, ServerInfo] = {}
# HTTPServer instance for the running daemon (set in run_daemon)
_DAEMON_SERVER: Optional[HTTPServer] = None


def _log_path_for(projects_dir: str, port: int) -> str:
    try:
        basedir = os.path.join(projects_dir, ".mcp_grok_daemon_logs")
        os.makedirs(basedir, exist_ok=True)
        return os.path.join(basedir, f"mcp_grok_{port}.log")
    except Exception:
        # fallback to /tmp
        return os.path.join("/tmp", f"mcp_grok_{port}.log")


def _start_server_proc(port: int, projects_dir: Optional[str] = None) -> ServerInfo:
    projects_dir = projects_dir or config.projects_dir
    logfile = _log_path_for(projects_dir, port)
    logf = open(logfile, "a+")
    cmd = [
        "mcp-grok-server",
        "--port",
        str(port),
        "--projects-dir",
        projects_dir,
    ]
    proc = subprocess.Popen(cmd, stdout=logf, stderr=logf, start_new_session=True)
    info = ServerInfo(
        pid=proc.pid,
        port=port,
        projects_dir=projects_dir,
        logfile=logfile,
        started_at=time.time(),
        proc=proc
    )
    with _SERVERS_LOCK:
        _SERVERS[proc.pid] = info
    return info


def _stop_server_proc_by_pid(pid: int) -> bool:
    with _SERVERS_LOCK:
        info = _SERVERS.get(pid)
    if not info:
        # try best-effort OS kill
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False
    try:
        # Prefer proc.terminate/poll/wait
        proc_obj = getattr(info, 'proc', None)
        if proc_obj is not None:
            if proc_obj.poll() is None:
                proc_obj.terminate()
                try:
                    proc_obj.wait(timeout=2)
                except Exception:
                    proc_obj.kill()
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.2)
            try:
                os.kill(pid, 0)
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    except Exception:
        return False
    finally:
        with _SERVERS_LOCK:
            _SERVERS.pop(pid, None)
    return True


def _stop_server_proc_by_port(port: int) -> bool:
    with _SERVERS_LOCK:
        for pid, info in list(_SERVERS.items()):
            if info.port == port:
                return _stop_server_proc_by_pid(pid)
    return False


def _list_servers() -> Dict[str, Any]:
    with _SERVERS_LOCK:
        return {str(pid): info.to_dict() for pid, info in _SERVERS.items()}


def _stop_all() -> int:
    with _SERVERS_LOCK:
        pids = list(_SERVERS.keys())
    count = 0
    for pid in pids:
        if _stop_server_proc_by_pid(pid):
            count += 1
    return count


class _Handler(BaseHTTPRequestHandler):
    def _send_json(self, code: int, payload: Any):
        payload_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def do_GET(self):
        if self.path == "/list":
            data = {"servers": _list_servers()}
            self._send_json(200, data)
        else:
            self._send_json(404, {"error": "not found"})

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            return json.loads(body)
        except Exception:
            return {}

    def _handle_start(self, payload: dict):
        port = int(payload.get("port") or 0)
        projects_dir = payload.get("projects_dir")
        if not port:
            return self._send_json(400, {"error": "port required"})
        try:
            info = _start_server_proc(port, projects_dir)
            return self._send_json(200, {"result": info.to_dict()})
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

    def _handle_stop_all(self):
        count = _stop_all()
        return self._send_json(200, {"stopped": count})

    def _handle_daemon_stop(self):
        # Respond first, then stop the HTTP server cleanly.
        self._send_json(200, {"result": "stopping"})
        try:
            daemon: Optional[HTTPServer] = _DAEMON_SERVER
            if daemon is not None:
                # Shutdown in a new thread so we can return the response
                threading.Thread(target=daemon.shutdown, daemon=True).start()
        except Exception:
            pass
        return

    def _handle_server_stop(self, payload: dict):
        pid = payload.get("pid")
        port = payload.get("port")
        ok = False
        if pid is not None:
            try:
                ok = _stop_server_proc_by_pid(int(pid))
            except Exception:
                ok = False
        elif port is not None:
            try:
                ok = _stop_server_proc_by_port(int(port))
            except Exception:
                ok = False
        else:
            return self._send_json(400, {"error": "pid or port required"})
        return self._send_json(200, {"result": bool(ok)})

    def do_POST(self):
        payload = self._read_json_body()

        if self.path == "/start":
            return self._handle_start(payload)

        if self.path == "/stop_all":
            return self._handle_stop_all()

        if self.path == "/daemon/stop":
            return self._handle_daemon_stop()

        if self.path == "/server/stop":
            return self._handle_server_stop(payload)

        return self._send_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        # reduce noise in test output
        return


def run_daemon(host: str = HOST, port: int = DAEMON_PORT):
    global _DAEMON_SERVER
    server = HTTPServer((host, port), _Handler)
    _DAEMON_SERVER = server
    try:
        print(f"Server daemon listening on http://{host}:{port}")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            _stop_all()
        except Exception:
            pass
        try:
            server.server_close()
        finally:
            _DAEMON_SERVER = None


if __name__ == "__main__":
    run_daemon()
