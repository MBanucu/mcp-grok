from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Tuple, cast

if TYPE_CHECKING:
    from .server_daemon import ServerDaemon


def parse_start_params(
    payload: dict
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    port_raw = payload.get("port")
    port = int(port_raw) if port_raw is not None else None
    projects_dir_raw = payload.get("projects_dir")
    if projects_dir_raw is not None and not isinstance(projects_dir_raw, str):
        raise TypeError("projects_dir must be str or None")
    projects_dir: Optional[str] = projects_dir_raw
    if port is None or port == 0:
        return None, projects_dir, "port required"
    return port, projects_dir, None


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
        elif self.path == "/proxy/list":
            data = {"proxies": self.daemon._list_proxies()}
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
        try:
            info = self.daemon._start_server_proc(cast(int, port), projects_dir)
            return self._send_json(200, {"result": info.to_dict()})
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

    def _handle_proxy_start(self, payload: Dict[str, Any]) -> None:
        port_raw = payload.get("port")
        port = int(port_raw) if port_raw is not None else 3006  # default port
        if port == 0:
            return self._send_json(400, {"error": "port required"})
        try:
            info = self.daemon._start_proxy_proc(port)
            return self._send_json(200, {"result": info.to_dict()})
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

    def _handle_stop_all(self) -> None:
        count = self.daemon._stop_all()
        return self._send_json(200, {"stopped": count})

    def _handle_daemon_stop(self) -> None:
        self._send_json(200, {"result": "stopping"})
        try:
            self.daemon._stop_all()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        except Exception:
            pass

    def _handle_server_stop(self, payload: Dict[str, Any]) -> None:
        pid, port, error = self._parse_stop_server_params(payload)
        if error:
            return self._send_json(400, {"error": error})
        if pid is not None:
            return self._do_server_stop_by_pid(pid)
        if port is not None:
            return self._do_server_stop_by_port(port)
        return self._send_json(400, {"error": "No valid pid or port provided"})

    def _handle_proxy_stop(self, payload: Dict[str, Any]) -> None:
        pid, port, error = self._parse_stop_server_params(payload)  # reuse the same parsing
        if error:
            return self._send_json(400, {"error": error})
        if pid is not None:
            return self._do_proxy_stop_by_pid(pid)
        if port is not None:
            return self._do_proxy_stop_by_port(port)
        return self._send_json(400, {"error": "No valid pid or port provided"})

    def _do_proxy_stop_by_pid(self, pid: int) -> None:
        try:
            ok = self.daemon._stop_proxy_proc_by_pid(pid)
        except Exception:
            ok = False
        return self._send_json(200, {"result": bool(ok)})

    def _do_proxy_stop_by_port(self, port: int) -> None:
        try:
            ok = self.daemon._stop_proxy_proc_by_port(port)
        except Exception:
            ok = False
        return self._send_json(200, {"result": bool(ok)})

    def _parse_stop_server_params(
        self, payload: Dict[str, Any]
    ) -> Tuple[Optional[int], Optional[int], Optional[str]]:
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
        if self.path == "/proxy/start":
            return self._handle_proxy_start(payload)
        if self.path == "/proxy/stop":
            return self._handle_proxy_stop(payload)
        if self.path == "/stop_all":
            return self._handle_stop_all()
        if self.path == "/daemon/stop":
            return self._handle_daemon_stop()
        if self.path == "/server/stop":
            return self._handle_server_stop(payload)
        return self._send_json(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:
        return


def make_handler(
    daemon: 'ServerDaemon'
) -> Callable[..., 'ServerDaemonHandler']:
    """
    Factory returning a handler class bound to provided daemon instance.
    This binds 'self.daemon' in each request handler instance, using closure scope,
    and avoids nonstandard signature hacks
    (required for http.server compatibility).
    """
    return lambda *args, **kwargs: ServerDaemonHandler(daemon, *args, **kwargs)
