"""
Minimal server daemon for managing mcp-grok-server subprocesses.

Exposes a JSON HTTP API (start, stop, list, stop_all)
for process/port lifecycle management, without global
mutable state.

All request handlers are constructed with the controlling
ServerDaemon instance via make_handler(daemon). This
ensures correct modularity and testability, and avoids
nonstandard HTTPServer hacks.

Intended for use by tests via mcp_grok.server_client.
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import threading
import os
import subprocess
import signal
import time
import datetime
from typing import Dict, Any, Optional, TypedDict, Callable, Tuple, cast

from .server_client import DEFAULT_DAEMON_PORT
from .config import config


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


def parse_start_params(payload: dict) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    port_raw = payload.get("port")
    port = int(port_raw) if port_raw is not None else None
    projects_dir_raw = payload.get("projects_dir")
    if projects_dir_raw is not None and not isinstance(projects_dir_raw, str):
        raise TypeError("projects_dir must be str or None")
    projects_dir: Optional[str] = projects_dir_raw
    if port is None or port == 0:
        return None, projects_dir, "port required"
    return port, projects_dir, None


def do_start_server(handler: 'ServerDaemonHandler', port: int, projects_dir: Optional[str]) -> None:
    assert port is not None
    try:
        info = handler.daemon._start_server_proc(cast(int, port), projects_dir)
        return handler._send_json(200, {"result": info.to_dict()})
    except Exception as e:
        return handler._send_json(500, {"error": str(e)})


class ServerDaemonHandler(BaseHTTPRequestHandler):

    def __init__(self, daemon: 'ServerDaemon', *args, **kwargs) -> None:
        self.daemon = daemon
        super().__init__(*args, **kwargs)

    def _send_json(self, code: int, payload: Any) -> None:
        payload_bytes = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload_bytes)))
        self.end_headers()
        self.wfile.write(payload_bytes)

    def do_GET(self) -> None:
        if self.path == "/list":
            data = {"servers": self.daemon._list_servers()}
            self._send_json(200, data)
        else:
            self._send_json(404, {"error": "not found"})

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            return json.loads(body)
        except Exception:
            return {}

    def _handle_start(self, payload: Dict[str, Any]) -> None:
        port, projects_dir, error = parse_start_params(payload)
        if error:
            return self._send_json(400, {"error": error})
        assert port is not None  # Since error would have been returned
        return do_start_server(self, cast(int, port), projects_dir)

    def _handle_stop_all(self) -> None:
        count = self.daemon._stop_all()
        return self._send_json(200, {"stopped": count})

    def _handle_daemon_stop(self) -> None:
        self._send_json(200, {"result": "stopping"})
        try:
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        except Exception:
            pass
        return

    def _handle_server_stop(self, payload: Dict[str, Any]) -> None:
        pid, port, error = self._parse_stop_server_params(payload)
        if error:
            return self._send_json(400, {"error": error})
        if pid is not None:
            return self._do_server_stop_by_pid(pid)
        if port is not None:
            return self._do_server_stop_by_port(port)
        return self._send_json(400, {"error": "No valid pid or port provided"})

    def _parse_stop_server_params(self, payload: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], Optional[str]]:
        pid = payload.get("pid")
        port = payload.get("port")
        if pid is not None:
            try:
                pid = int(pid)
            except Exception:
                pid = None
        if port is not None:
            try:
                port = int(port)
            except Exception:
                port = None
        if pid is None and port is None:
            return None, None, "pid or port required"
        return pid, port, None

    def _do_server_stop_by_pid(self, pid: int) -> None:
        try:
            ok = self.daemon._stop_server_proc_by_pid(pid)
        except Exception:
            ok = False
        return self._send_json(200, {"result": bool(ok)})

    def _do_server_stop_by_port(self, port: int) -> None:
        try:
            ok = self.daemon._stop_server_proc_by_port(port)
        except Exception:
            ok = False
        return self._send_json(200, {"result": bool(ok)})

    def do_POST(self) -> None:
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

    def log_message(self, format: str, *args) -> None:
        return


def make_handler(daemon: 'ServerDaemon') -> Callable[..., 'ServerDaemonHandler']:
    """
    Factory returning a handler class bound to provided daemon instance.
    This binds 'self.daemon' in each request handler instance, using closure scope,
    and avoids nonstandard signature hacks
    (required for http.server compatibility).
    """
    return lambda *args, **kwargs: ServerDaemonHandler(daemon, *args, **kwargs)

# The server always uses an instance-bound handler via make_handler(self).


class ServerDaemonHTTPServer(HTTPServer):

    def __init__(self, server_address, RequestHandlerClass, daemon: 'ServerDaemon') -> None:
        super().__init__(server_address, RequestHandlerClass)
        self.daemon = daemon  # Still available if further extension is required.

    def finish_request(self, request, client_address) -> None:
        self.RequestHandlerClass(request, client_address, self)


class ServerDaemon:

    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_DAEMON_PORT) -> None:
        self.host = host
        self.port = port
        self._servers: Dict[int, ServerInfo] = {}
        self._servers_lock = threading.Lock()
        self.httpd: Optional[HTTPServer] = None

    def _log_path_for(self, port: int, timestamp: str) -> str:
        path = os.path.expanduser(f'~/.mcp-grok/{timestamp}_{port}_mcp-server.log')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _start_server_proc(self, port: int, projects_dir: Optional[str] = None) -> ServerInfo:
        now = datetime.datetime.now()
        started_at = now.timestamp()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        projects_dir = projects_dir or config.projects_dir
        logfile = self._log_path_for(port, timestamp_str)
        logf = open(logfile, "a+")
        cmd = [
            "mcp-grok-server", "--port", str(port), "--projects-dir", projects_dir,
            "--audit-log", config.server_audit_log,
        ]
        proc = subprocess.Popen(cmd, stdout=logf, stderr=logf, start_new_session=True)
        info = ServerInfo(
            pid=proc.pid,
            port=port,
            projects_dir=projects_dir,
            logfile=logfile,
            started_at=started_at,
            audit_log=config.server_audit_log,
            proc=proc
        )
        with self._servers_lock:
            self._servers[proc.pid] = info
        return info

    def _stop_server_proc_by_pid(self, pid: int) -> bool:
        with self._servers_lock:
            info = self._servers.get(pid)
        if not info:
            return self._os_kill_pid(pid)
        return self._stop_info_proc(pid, info)

    def _os_kill_pid(self, pid: int) -> bool:
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except Exception:
            return False

    def _stop_info_proc(self, pid: int, info: ServerInfo) -> bool:
        try:
            proc_obj = getattr(info, 'proc', None)
            if proc_obj is not None:
                return self._terminate_proc_obj(proc_obj)
            else:
                self._os_kill_pid(pid)
                time.sleep(0.2)
                try:
                    os.kill(pid, 0)
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
        except Exception:
            return False
        finally:
            with self._servers_lock:
                self._servers.pop(pid, None)
        return True

    def _terminate_proc_obj(self, proc_obj: subprocess.Popen) -> bool:
        try:
            if proc_obj.poll() is None:
                proc_obj.terminate()
                try:
                    proc_obj.wait(timeout=2)
                except Exception:
                    proc_obj.kill()
            return True
        except Exception:
            return False

    def _stop_server_proc_by_port(self, port: int) -> bool:
        with self._servers_lock:
            for pid, info in list(self._servers.items()):
                if info.port == port:
                    return self._stop_server_proc_by_pid(pid)
        return False

    def _list_servers(self) -> dict[str, ServerInfoDict]:
        with self._servers_lock:
            return {str(pid): info.to_dict() for pid, info in self._servers.items()}

    def _stop_all(self) -> int:
        with self._servers_lock:
            pids = list(self._servers.keys())
        count = 0
        for pid in pids:
            if self._stop_server_proc_by_pid(pid):
                count += 1
        return count

    def run(self) -> None:
        # Always use handler factory to provide daemon instance context to all HTTP requests
        handler_class = make_handler(self)
        self.httpd = ServerDaemonHTTPServer((self.host, self.port), handler_class, self)
        try:
            print(f"Server daemon listening on http://{self.host}:{self.port}")
            self.httpd.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                self._stop_all()
            except Exception:
                pass
            try:
                self.httpd.server_close()
            finally:
                self.httpd = None

    def shutdown(self) -> None:
        if self.httpd:
            self.httpd.shutdown()


def run_daemon(host: str = "127.0.0.1", port: int = DEFAULT_DAEMON_PORT) -> None:
    daemon = ServerDaemon(host, port)
    daemon.run()


if __name__ == "__main__":
    run_daemon()
