import tempfile
import subprocess
import pytest
from mcp_grok import server_client


def pick_free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def server_daemon_proc():
    daemon_port = pick_free_port()
    projects_dir = tempfile.mkdtemp(prefix="mcp_test_projects_")

    proc = subprocess.Popen([
        'mcp-grok-daemon',
        '--host', '127.0.0.1', '--port', str(daemon_port)
    ])

    # Wait for daemon to start
    import time as _time
    import socket as _socket
    start = _time.time()
    while True:
        try:
            with _socket.create_connection(("127.0.0.1", daemon_port), timeout=0.5):
                break
        except Exception:
            _time.sleep(0.05)
        if _time.time() - start > 10:
            raise RuntimeError(f"Timed out waiting for daemon on port {daemon_port}")
    yield {
        "port": daemon_port,
        "projects_dir": projects_dir,
    }
    # Stop the daemon
    server_client.stop_daemon(daemon_port=daemon_port)
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def mcp_server(server_daemon_proc):
    daemon_port = server_daemon_proc["port"]
    projects_dir = server_daemon_proc["projects_dir"]
    server_port = pick_free_port()
    resp = server_client.start_server(port=server_port, projects_dir=projects_dir, daemon_port=daemon_port)
    info = resp["result"]
    import time as _t
    import socket as _s
    addr = ("127.0.0.1", server_port)
    ready = False
    for _ in range(100):
        try:
            with _s.create_connection(addr, timeout=0.2):
                ready = True
                break
        except Exception:
            _t.sleep(0.1)
    if not ready:
        raise RuntimeError(f"Managed server on port {server_port} not ready after 10 sec")
    yield {
        "url": f"http://localhost:{server_port}/mcp",
        "projects_dir": projects_dir
    }
    # Stop the managed server
    server_client.stop_managed_server(pid=info["pid"], daemon_port=daemon_port)
