import os
import time
import pytest
from menu import menu_core
from mcp_grok.config import config


@pytest.fixture
def start_stop_server():
    """
    Fixture to start/stop the server process for tests.
    Returns the process object.
    """
    TEST_PORT = 8099
    proc = menu_core.server_manager.start_server(port=TEST_PORT)
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
    proc = start_stop_server
    # If proc is None, server is already running; just check log exists and is nonempty
    if proc is None:
        if not os.path.exists(config.mcp_shell_log):
            pytest.fail("Server is already running but mcp_server.log does not exist under this CWD; skipping log file check.")
        with open(config.mcp_shell_log, "r") as f:
            assert f.read().strip(), "Log file is empty even though server is running."
    else:
        wait_for_log(config.mcp_shell_log, timeout=10.0)  # usually instant, but waits up to 10s


def test_proxy_log(start_stop_proxy):
    wait_for_log(config.proxy_log, timeout=30.0)


def test_clear_mcp_log():
    # Write something, then clear
    with open(config.mcp_shell_log, 'w') as f:
        f.write('some text\n')
    menu_core.clear_log(config.mcp_shell_log)
    with open(config.mcp_shell_log, 'r') as f:
        assert f.read() == '', "MCP log not cleared"


def test_clear_proxy_log():
    # Write something, then clear
    with open(config.proxy_log, 'w') as f:
        f.write('other text\n')
    menu_core.clear_log(config.proxy_log)
    with open(config.proxy_log, 'r') as f:
        assert f.read() == '', "Proxy log not cleared"


def test_proxy_log_config_error(start_stop_proxy):
    """Fail if the proxy logs a config error within 3 seconds of startup."""
    start = time.time()
    max_wait = 3.0  # lowered from 10s for faster CI/dev
    poll_interval = 0.1
    error_found = False
    while time.time() - start < max_wait:
        if os.path.exists(config.proxy_log):
            with open(config.proxy_log, "r") as f:
                text = f.read()
                if "Failed to load config" in text or "Error: Invalid config format" in text:
                    error_found = True
                    break
        time.sleep(poll_interval)
    assert not error_found, "Proxy log reports a config loading error!"


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

import socket

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

def test_server_listens_on_specified_port():
    """Test that after launching, the server listens on the specified port."""
    TEST_PORT = 8108  # Should be a free port for test runs!
    proc = menu_core.server_manager.start_server(port=TEST_PORT)
    assert proc is not None, "start_server did not return a process object"
    try:
        port_ready = wait_for_port(TEST_PORT, timeout=5.0)
        assert port_ready, f"Server did not listen on port {TEST_PORT} in time"
    finally:
        menu_core.server_manager.stop_server()

def test_start_server_runs_and_stops():
    TEST_PORT = 8099
    proc = menu_core.server_manager.start_server(port=TEST_PORT)
    assert proc is not None, "start_server did not return a process object"
    try:
        assert proc.poll() is None, "Server process exited prematurely after start"
    finally:
        menu_core.server_manager.stop_server()
        assert proc.poll() is not None, "Server process did not stop after stop_server called"
