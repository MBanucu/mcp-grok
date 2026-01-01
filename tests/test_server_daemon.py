import socket
import time
import threading
from http.server import HTTPServer

import pytest

from mcp_grok import server_daemon
from mcp_grok import server_client


def pick_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _FakePopen:
    _next = 200000
    _instances = {}

    def __init__(self, cmd, stdout=None, stderr=None, start_new_session=False):
        # assign a high pid that is unlikely to exist
        self.pid = _FakePopen._next
        _FakePopen._next += 1
        self.args = cmd
        self._sock = None
        # try to parse --port value from cmd
        try:
            if isinstance(cmd, (list, tuple)):
                if "--port" in cmd:
                    idx = cmd.index("--port")
                    port = int(cmd[idx + 1])
                    self._start_listening(port)
        except Exception:
            pass
        _FakePopen._instances[self.pid] = self

    def _start_listening(self, port):
        import socket
        import threading

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", port))
        s.listen(5)
        self._sock = s

        def _accept_loop(sock):
            try:
                while True:
                    conn, _ = sock.accept()
                    try:
                        conn.close()
                    except Exception:
                        pass
            except Exception:
                pass

        t = threading.Thread(target=_accept_loop, args=(s,), daemon=True)
        t.start()

    def close(self):
        try:
            if self._sock:
                self._sock.close()
                self._sock = None
        except Exception:
            pass

    @classmethod
    def kill(cls, pid, sig):
        inst = cls._instances.get(pid)
        if inst:
            inst.close()
            # remove instance
            try:
                del cls._instances[pid]
            except Exception:
                pass
        # don't actually raise
        return


def _wait_for_port(port, timeout=3.0):
    start = time.time()
    while True:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except Exception:
            time.sleep(0.05)
        if time.time() - start > timeout:
            return False


def test_daemon_start_list_stop(monkeypatch, tmp_path):
    daemon_port = pick_free_port()
    server_port = pick_free_port()

    # Monkeypatch Popen and os.kill to avoid starting real processes
    monkeypatch.setattr(server_daemon.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(server_daemon.os, "kill", _FakePopen.kill)


    thread = threading.Thread(
        target=lambda: server_daemon.run_daemon(host="127.0.0.1", port=daemon_port),
        daemon=True,
    )
    thread.start()

    try:
        assert _wait_for_port(daemon_port), "Daemon did not start in time"

        # Start a managed server via the daemon
        resp = server_client.start_server(port=server_port, projects_dir=str(tmp_path), daemon_port=daemon_port)
        assert isinstance(resp, dict) and "result" in resp
        info = resp["result"]
        pid = info["pid"]

        # List servers
        listing = server_client.list_servers(daemon_port=daemon_port)
        assert str(pid) in listing.get("servers", {})

        # Stop the managed server
        stop_resp = server_client.stop_managed_server(pid=pid, daemon_port=daemon_port)
        assert stop_resp.get("result") is True

        # Stop the daemon via its API
        stopd = server_client.stop_daemon(daemon_port=daemon_port)
        assert stopd.get("result") == "stopping"

        # Wait for the daemon thread to exit
        thread.join(timeout=2)
        assert not thread.is_alive(), "Daemon thread did not exit after stop"

    finally:
        # Ensure clean shutdown if something went wrong
        try:
            if thread.is_alive():
                srv = getattr(server_daemon, "_DAEMON_SERVER", None)
                if srv is not None:
                    try:
                        srv.shutdown()
                    except Exception:
                        pass
                thread.join(timeout=1)
        except Exception:
            pass


def test_run_daemon_stop_removes_managed_servers(monkeypatch, tmp_path):
    """Start daemon, start two managed servers, stop daemon, ensure servers removed."""
    daemon_port = pick_free_port()
    sp1 = pick_free_port()
    sp2 = pick_free_port()

    thread = threading.Thread(
        target=lambda: server_daemon.run_daemon(host="127.0.0.1", port=daemon_port),
        daemon=True,
    )
    thread.start()

    try:
        assert _wait_for_port(daemon_port), "Daemon did not start in time"

        r1 = server_client.start_server(port=sp1, projects_dir=str(tmp_path), daemon_port=daemon_port)
        r2 = server_client.start_server(port=sp2, projects_dir=str(tmp_path), daemon_port=daemon_port)
        pid1 = r1["result"]["pid"]
        pid2 = r2["result"]["pid"]

        listing = server_client.list_servers(daemon_port=daemon_port)
        assert str(pid1) in listing.get("servers", {})
        assert str(pid2) in listing.get("servers", {})

        # Check that the managed server ports are accepting connections
        assert _wait_for_port(sp1), f"Managed server port {sp1} not accepting connections"
        assert _wait_for_port(sp2), f"Managed server port {sp2} not accepting connections"

        # Stop daemon
        stopd = server_client.stop_daemon(daemon_port=daemon_port)
        assert stopd.get("result") == "stopping"

        thread.join(timeout=2)
        assert not thread.is_alive(), "Daemon thread did not exit after stop"

        # After stopping the daemon, both managed server ports should be down.
        # Wait up to 2 seconds for each port to close (to avoid flakes).
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if not _wait_for_port(sp1, timeout=0.2) and not _wait_for_port(sp2, timeout=0.2):
                break
            time.sleep(0.05)
        assert not _wait_for_port(sp1, timeout=0.02), f"Managed server port {sp1} should be down"
        assert not _wait_for_port(sp2, timeout=0.02), f"Managed server port {sp2} should be down"

        # After daemon stops, the registry should be empty
        # Access directly for test validation
        remaining = list(server_daemon._SERVERS.keys())
        assert remaining == []

    finally:
        try:
            srv = getattr(server_daemon, "_DAEMON_SERVER", None)
            if srv is not None:
                try:
                    srv.shutdown()
                except Exception:
                    pass
            thread.join(timeout=1)
        except Exception:
            pass
