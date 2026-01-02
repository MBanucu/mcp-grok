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
try:
    import psutil
except ImportError:
    psutil = None
from http.server import HTTPServer
import threading
import os
import datetime
import argparse
import subprocess
import signal
import time
from typing import Dict, Optional

from .server_info import ServerInfo, ServerInfoDict, ProxyInfo, ProxyInfoDict

from .server_daemon_handler import make_handler

from .server_client import DEFAULT_DAEMON_PORT
from .config import config

from menu.proxy_manager import ProxyManager


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
        self._proxies: Dict[int, ProxyInfo] = {}
        self._proxies_lock = threading.Lock()
        self.httpd: Optional[HTTPServer] = None

    def _log_path_for(self, port: int, timestamp: str) -> str:
        path = os.path.expanduser(f'~/.mcp-grok/{timestamp}_{port}_mcp-server.log')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _audit_log_path_for(self, port: int, timestamp: str) -> str:
        path = os.path.expanduser(f'~/.mcp-grok/{timestamp}_{port}_audit.log')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def _start_server_proc(self, port: int, projects_dir: Optional[str] = None) -> ServerInfo:
        now = datetime.datetime.now()
        started_at = now.timestamp()
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        projects_dir = projects_dir or config.projects_dir
        logfile = self._log_path_for(port, timestamp_str)
        audit_logfile = self._audit_log_path_for(port, timestamp_str)
        logf = open(logfile, "a+")
        cmd = [
            "mcp-grok-server", "--port", str(port), "--projects-dir", projects_dir,
            "--audit-log", audit_logfile,
        ]
        proc = subprocess.Popen(cmd, stdout=logf, stderr=logf, start_new_session=True)
        info = ServerInfo(
            pid=proc.pid,
            port=port,
            projects_dir=projects_dir,
            logfile=logfile,
            started_at=started_at,
            audit_log=audit_logfile,
            proc=proc
        )
        with self._servers_lock:
            self._servers[proc.pid] = info
        return info

    def _start_proxy_proc(self, port: int, config_json=None) -> ProxyInfo:
        now = datetime.datetime.now()
        started_at = now.timestamp()
        logfile = self._log_path_for(port, now.strftime("%Y%m%d_%H%M%S"))
        config_path = None
        if config_json:
            import tempfile
            import json
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                if isinstance(config_json, str):
                    config_data = json.loads(config_json)
                else:
                    config_data = config_json
                json.dump(config_data, f)
                config_path = f.name
        proxy_manager = ProxyManager(config_path=config_path, port=port)
        proc = proxy_manager.start_proxy()
        info = ProxyInfo(
            pid=proc.pid,
            port=port,
            logfile=logfile,
            started_at=started_at,
            proc=proc,
            proxy_manager=proxy_manager,
            config_path=config_path
        )
        with self._proxies_lock:
            self._proxies[proc.pid] = info
        return info

    def _stop_proxy_proc_by_pid(self, pid: int) -> bool:
        with self._proxies_lock:
            info = self._proxies.get(pid)
        if not info:
            return self._os_kill_pid(pid)
        return self._stop_proxy_info_proc(pid, info)

    def _stop_proxy_info_proc(self, pid: int, info: ProxyInfo) -> bool:
        try:
            info.proxy_manager.stop_proxy()
            return True
        except Exception:
            return False
        finally:
            if info.config_path and os.path.exists(info.config_path):
                os.unlink(info.config_path)
            with self._proxies_lock:
                self._proxies.pop(pid, None)

    def _stop_proxy_proc_by_port(self, port: int) -> bool:
        with self._proxies_lock:
            for pid, info in list(self._proxies.items()):
                if info.port == port:
                    return self._stop_proxy_proc_by_pid(pid)
        return False

    def _list_proxies(self) -> dict[str, ProxyInfoDict]:
        with self._proxies_lock:
            return {str(pid): info.to_dict() for pid, info in self._proxies.items()}

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
            server_pids = list(self._servers.keys())
        with self._proxies_lock:
            proxy_pids = list(self._proxies.keys())
        count = 0
        for pid in proxy_pids:
            if self._stop_proxy_proc_by_pid(pid):
                count += 1
        for pid in server_pids:
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


def main():
    parser = argparse.ArgumentParser(
        prog="mcp-grok-daemon",
        description="MCP Daemon for managing mcp-grok-server processes"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=DEFAULT_DAEMON_PORT,
        help='Port to run the daemon on'
    )
    parser.add_argument(
        '--host',
        type=str,
        default="127.0.0.1",
        help='Host to bind the daemon to'
    )
    args = parser.parse_args()
    run_daemon(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
