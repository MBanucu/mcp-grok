import os
import socket
import time
import threading
import subprocess
import re
import urllib.request
import json
import psutil
import pytest
from mcp_grok import server_daemon
from mcp_grok import server_client


def check_server_up(host: str, port: int, timeout=2.0) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return True
        except Exception:
            time.sleep(0.1)
    return False


def get_daemon_server_list(port):
    url = f"http://127.0.0.1:{port}/list"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            return json.load(resp).get("servers", {})
    except Exception as e:
        return {"error": str(e)}


@pytest.fixture(scope="module", autouse=True)
def check_servers_up_module(server_daemon_proc, mcp_server):
    # Check server_daemon_proc
    daemon_port = server_daemon_proc.get("port")
    assert daemon_port, "server_daemon_proc did not specify a port"
    assert _wait_for_port(daemon_port), (
        f"Server daemon from server_daemon_proc is not up at MODULE START (port={daemon_port})"
    )
    # Check mcp_server
    url = mcp_server.get("url")
    assert url, "mcp_server did not specify a url"
    m = re.search(r":(\d+)[^\d]", url)
    assert m, f"Could not extract port from mcp_server['url']: {url}"
    mcp_port = int(m.group(1))
    assert _wait_for_port(mcp_port), (
        f"mcp_server is not up at MODULE START (port={mcp_port})"
    )
    servers_at_start = get_daemon_server_list(daemon_port)
    print(f"Server list from daemon at MODULE START: {servers_at_start}")
    yield
    assert _wait_for_port(daemon_port), (
        f"Server daemon from server_daemon_proc went down at MODULE END (port={daemon_port})"
    )
    # If you expect mcp_server to be up:
    # assert _wait_for_port(mcp_port), f"mcp_server went down at MODULE END (port={mcp_port})"
    servers_at_end = get_daemon_server_list(daemon_port)
    print(f"Server list from daemon at MODULE END: {servers_at_end}")


@pytest.fixture(autouse=True)
def check_managed_servers_unchanged(server_daemon_proc):
    """Before and after each test, check daemon's server /list remains identical."""
    port = server_daemon_proc.get("port")
    assert port, "server_daemon_proc did not specify a port"
    servers_before = get_daemon_server_list(port)
    yield
    servers_after = get_daemon_server_list(port)
    assert servers_before == servers_after, (
        f"Managed servers changed during test!\n"
        f"Before: {servers_before}\n"
        f"After: {servers_after}"
    )


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
        self.pid = _FakePopen._next
        _FakePopen._next += 1
        self.args = cmd
        self._sock = None
        # Removed fake socket port opening for minimal stub
        _FakePopen._instances[self.pid] = self

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
            try:
                del cls._instances[pid]
            except Exception:
                pass
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


def _wait_for_process_exit(pid, timeout=2.0):
    """Wait for a process to exit using psutil."""
    try:
        p = psutil.Process(pid)
        p.wait(timeout=timeout)
    except psutil.NoSuchProcess:
        pass  # Already exited


def test_daemon_start_list_stop(monkeypatch, tmp_path):
    daemon_port = pick_free_port()
    server_port = pick_free_port()
    proc = subprocess.Popen([
        'mcp-grok-daemon',
        '--host', '127.0.0.1', '--port', str(daemon_port)
    ])
    try:
        print(f"Waiting for daemon on port {daemon_port}...")
        assert _wait_for_port(daemon_port), "Daemon did not start in time"
        print(f"Starting managed server on port {server_port}")
        resp = server_client.start_server(
            port=server_port,
            projects_dir=str(tmp_path),
            daemon_port=daemon_port
        )
        print(f"start_server resp: {resp}")
        assert isinstance(resp, dict) and "result" in resp
        info = resp["result"]
        pid = info["pid"]
        print(f"Managed server PID: {pid}")
        # Test that logfile is created
        logfile = info["logfile"]
        assert os.path.exists(logfile), f"Logfile {logfile} was not created"
        assert os.path.isfile(logfile), f"Logfile {logfile} is not a file"
        listing = server_client.list_servers(daemon_port=daemon_port)
        print(f"server list after start: {listing}")
        assert str(pid) in listing.get("servers", {})
        stop_resp = server_client.stop_managed_server(
            pid=pid,
            daemon_port=daemon_port
        )
        print(f"stop_managed_server resp: {stop_resp}")
        listing_post = server_client.list_servers(daemon_port=daemon_port)
        print(f"servers listing after stop: {listing_post}")
        # The old server_daemon._SERVERS direct access is removed; use server list endpoint instead.
        assert stop_resp.get("result") is True
        stopd = server_client.stop_daemon(daemon_port=daemon_port)
        print(f"daemon stop resp: {stopd}")
        assert stopd.get("result") == "stopping"
        proc.wait(timeout=5)
        print(f"Daemon proc poll: {proc.poll()}")
        assert proc.poll() is not None, "Daemon process did not exit"
    finally:
        # Ensure the daemon process is terminated even if assertions fail
        if proc.poll() is None:
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass  # Best-effort cleanup


def test_start_server_runs_and_stops(server_daemon_proc):
    """Test starting and stopping a server via the daemon."""
    daemon_port = server_daemon_proc["port"]
    projects_dir = server_daemon_proc["projects_dir"]
    server_port = pick_free_port()

    # Start server
    resp = server_client.start_server(port=server_port, projects_dir=projects_dir, daemon_port=daemon_port)
    assert resp["result"] is not None
    pid = resp["result"]["pid"]

    # Check it's in the list
    listing = server_client.list_servers(daemon_port=daemon_port)
    assert str(pid) in listing.get("servers", {})

    # Stop server
    stop_resp = server_client.stop_managed_server(pid=pid, daemon_port=daemon_port)
    assert stop_resp.get("result") is True

    # Wait for the process to exit
    _wait_for_process_exit(pid)

    # Check it's not in the list
    listing_after = server_client.list_servers(daemon_port=daemon_port)
    assert str(pid) not in listing_after.get("servers", {})


def test_server_listens_on_specified_port(server_daemon_proc):
    """Test that a server started via daemon listens on the specified port."""
    daemon_port = server_daemon_proc["port"]
    projects_dir = server_daemon_proc["projects_dir"]
    server_port = pick_free_port()

    resp = server_client.start_server(port=server_port, projects_dir=projects_dir, daemon_port=daemon_port)
    assert resp["result"] is not None
    pid = resp["result"]["pid"]

    # Check port is listening
    assert _wait_for_port(server_port), f"Server did not listen on port {server_port}"

    # Cleanup
    server_client.stop_managed_server(pid=pid, daemon_port=daemon_port)
    _wait_for_process_exit(pid)


def test_server_exits_on_bad_config(server_daemon_proc):
    """Test that starting a server with bad config (privileged port) causes it to exit."""
    daemon_port = server_daemon_proc["port"]
    projects_dir = server_daemon_proc["projects_dir"]
    bad_port = 1  # Privileged port, should cause server to exit

    resp = server_client.start_server(port=bad_port, projects_dir=projects_dir, daemon_port=daemon_port)
    assert resp["result"] is not None
    info = resp["result"]
    pid = info["pid"]
    logfile = info["logfile"]

    # Poll for the log to contain permission denied
    start = time.time()
    timeout = 2.0
    log_content = ""
    while time.time() - start < timeout:
        with open(logfile, 'r') as f:
            log_content = f.read()
            if "permission denied" in log_content.lower():
                break
        time.sleep(0.1)
    else:
        assert False, f"Expected 'permission denied' in logs within {timeout}s, got: {log_content}"

    # Check that the server does not bind to the privileged port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect(('127.0.0.1', bad_port))
            assert False, f"Server should not bind to privileged port {bad_port}"
        except ConnectionRefusedError:
            pass  # Expected

    # Cleanup (server should already be stopped)
    server_client.stop_managed_server(pid=pid, daemon_port=daemon_port)
    _wait_for_process_exit(pid)


def test_server_log(server_daemon_proc):
    """Test that a server started via daemon creates a log file."""
    daemon_port = server_daemon_proc["port"]
    projects_dir = server_daemon_proc["projects_dir"]
    server_port = pick_free_port()

    resp = server_client.start_server(port=server_port, projects_dir=projects_dir, daemon_port=daemon_port)
    assert resp["result"] is not None
    info = resp["result"]
    logfile = info["logfile"]

    # Check logfile exists
    assert os.path.exists(logfile), f"Logfile {logfile} was not created"
    assert os.path.isfile(logfile), f"Logfile {logfile} is not a file"

    # Poll for log content
    start = time.time()
    timeout = 2.0
    log_content = ""
    while time.time() - start < timeout:
        with open(logfile, 'r') as f:
            log_content = f.read()
            if "Server startup" in log_content:
                break
        time.sleep(0.1)
    else:
        assert False, f"Expected 'Server startup' in logs within {timeout}s, got: {log_content}"

    # Cleanup
    pid = info["pid"]
    server_client.stop_managed_server(pid=pid, daemon_port=daemon_port)
    _wait_for_process_exit(pid)


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
        print(f"Waiting for daemon on port {daemon_port}...")
        assert _wait_for_port(daemon_port), "Daemon did not start in time"
        print(f"Starting managed server 1 on port {sp1}")
        r1 = server_client.start_server(
            port=sp1,
            projects_dir=str(tmp_path),
            daemon_port=daemon_port
        )
        print(f"start_server 1 resp: {r1}")
        print(f"Starting managed server 2 on port {sp2}")
        r2 = server_client.start_server(
            port=sp2,
            projects_dir=str(tmp_path),
            daemon_port=daemon_port
        )
        print(f"start_server 2 resp: {r2}")
        pid1 = r1["result"]["pid"]
        pid2 = r2["result"]["pid"]
        print(f"Managed server PIDs: {pid1}, {pid2}")
        listing = server_client.list_servers(daemon_port=daemon_port)
        print(f"server list after start: {listing}")
        assert str(pid1) in listing.get("servers", {})
        assert str(pid2) in listing.get("servers", {})
        print(f"Checking connections to ports {sp1} and {sp2}")
        assert _wait_for_port(sp1), (
            f"Managed server port {sp1} not accepting connections"
        )
        assert _wait_for_port(sp2), (
            f"Managed server port {sp2} not accepting connections"
        )
        stopd = server_client.stop_daemon(daemon_port=daemon_port)
        print(f"daemon stop resp: {stopd}")
        assert stopd.get("result") == "stopping"
        thread.join(timeout=2)
        print(f"Daemon thread alive after stop: {thread.is_alive()}")
        assert not thread.is_alive(), "Daemon thread did not exit after stop"
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if (
                not _wait_for_port(sp1, timeout=0.2) and
                not _wait_for_port(sp2, timeout=0.2)
            ):
                break
            time.sleep(0.05)
        print(f"Port {sp1} up after daemon stop? {_wait_for_port(sp1, timeout=0.02)}")
        print(f"Port {sp2} up after daemon stop? {_wait_for_port(sp2, timeout=0.02)}")
        assert not _wait_for_port(sp1, timeout=0.02), (
            f"Managed server port {sp1} should be down"
        )
        assert not _wait_for_port(sp2, timeout=0.02), (
            f"Managed server port {sp2} should be down"
        )
        # Use the handler endpoint instead of direct _SERVERS access
        servers_after_stop = get_daemon_server_list(daemon_port)
        print(f"Remaining managed servers after daemon stop: {list(servers_after_stop.keys())}")
        # Accept either an empty servers dict (normal), or error (daemon exited)
        if 'error' in servers_after_stop:
            assert True  # Daemon is dead, expected
        else:
            assert list(servers_after_stop.keys()) == []
    finally:
        try:
            srv = getattr(server_daemon, "_DAEMON_SERVER", None)
            print("Attempting daemon shutdown from finally block...")
            if srv is not None:
                try:
                    srv.shutdown()
                except Exception:
                    print("Exception during daemon shutdown.")
            thread.join(timeout=1)
        except Exception:
            print("Exception during final cleanup.")
