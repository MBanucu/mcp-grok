import os
import shutil
import time
import pytest
import socket
from menu import menu_core
from mcp_grok.config import config


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


FREE_PORT = get_free_port()
config.port = FREE_PORT  # Dynamically select a free port for this test module


@pytest.fixture(scope="module")
def start_stop_server():
    """
    Fixture to start/stop the server process for tests.
    Returns the process object.
    """
    proc = menu_core.server_manager.start_server(port=FREE_PORT)
    yield proc
    if proc is not None:
        menu_core.server_manager.stop_server()


@pytest.fixture(scope="module")
def start_stop_proxy():
    """
    Fixture to start/stop the proxy process for tests.
    Returns the process object.
    """
    proc = menu_core.start_proxy()
    yield proc
    menu_core.stop_proxy(proc)


def wait_for_log(log_file, timeout=10.0, poll_interval=0.2):
    """Wait up to timeout seconds for the log to become nonempty."""
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                if f.read().strip():
                    return
        time.sleep(poll_interval)
    raise AssertionError(f"Log file {log_file} did not become nonempty within {timeout} seconds.")


def test_server_log(start_stop_server):
    # Always wait for the log up to 10 seconds, regardless of server status
    log_path = os.path.expanduser(f'~/.mcp-grok/{config.log_timestamp}_{config.port}_mcp-shell.log')
    wait_for_log(log_path, timeout=10.0)


@pytest.mark.skipif(not shutil.which('superassistant-proxy'), reason="superassistant-proxy not available")
def test_proxy_log(start_stop_proxy):
    wait_for_log(config.proxy_log, timeout=30.0)


@pytest.mark.skipif(not shutil.which('superassistant-proxy'), reason="superassistant-proxy not available")
def test_proxy_log_config_error(start_stop_proxy):
    """
    Fail on config error after proxy start. Print log for success marker.
    """
    from pathlib import Path

    max_wait = 10.0
    poll_interval = 0.05
    error_found = False
    log_path = Path(config.proxy_log)
    success_marker = "[mcp-superassistant-proxy] Loaded config with 1 servers"
    success_marker_found = False

    poll_start = time.perf_counter()

    while time.perf_counter() - poll_start < max_wait:
        if log_path.exists():
            with open(log_path, "r") as f:
                text = f.read()
                if "Failed to load config" in text or "Error: Invalid config format" in text:
                    error_found = True
                    break
                if success_marker in text:
                    success_marker_found = True
                    break
        time.sleep(poll_interval)
    assert not error_found, "Proxy log reports a config loading error!"
    assert success_marker_found, f"Proxy log did not contain the success marker within {max_wait} seconds!"


def test_server_exits_on_bad_config():
    """
    Ensure server process dies quickly and cleanly if started with a bad port or config.
    """
    BAD_PORT = 1  # Privileged, reserved port; will fail to bind except as root
    proc = menu_core.server_manager.start_server(port=BAD_PORT)
    if proc is None:
        pytest.skip("Cannot test: port 1 is already in use (possibly by another system process)")
    try:
        total_wait = 0.0
        interval = 0.05
        max_wait = 4.0
        while proc.poll() is None and total_wait < max_wait:
            time.sleep(interval)
            total_wait += interval
        assert proc.poll() is not None, "Server did not exit with bad config (port 1)!"
    finally:
        menu_core.server_manager.stop_server()


def wait_for_port(port, timeout=5.0, poll_interval=0.05):
    """Wait up to timeout seconds for a TCP port to be open on localhost."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.2):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(poll_interval)
    return False


def test_server_listens_on_specified_port(start_stop_server):
    """Test that after launching, the server listens on the specified port."""
    port_ready = wait_for_port(FREE_PORT, timeout=5.0)
    assert port_ready, f"Server did not listen on port {FREE_PORT} in time"


def test_start_server_runs_and_stops():
    # This test still uses a separate port for isolation
    TEST_PORT = get_free_port()
    proc = menu_core.server_manager.start_server(port=TEST_PORT)
    assert proc is not None, "start_server did not return a process object"
    try:
        assert proc.poll() is None, "Server process exited prematurely after start"
    finally:
        menu_core.server_manager.stop_server()
        assert proc.poll() is not None, "Server process did not stop after stop_server called"
