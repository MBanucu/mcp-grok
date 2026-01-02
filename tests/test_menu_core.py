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
def start_stop_proxy():
    """
    Fixture to start/stop the proxy process for tests.
    Returns the process object.
    """
    try:
        proc = menu_core.start_proxy()
    except FileNotFoundError as e:
        raise RuntimeError(f"superassistant-proxy executable not found. Please ensure it is installed and in PATH. Error: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to start superassistant-proxy: {e}")
    yield proc
    menu_core.stop_proxy(proc)


def test_proxy_log(start_stop_proxy):
    wait_for_log(config.proxy_log, timeout=30.0)


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


def wait_for_log(log_file, timeout=10.0, poll_interval=0.2):
    """Wait up to timeout seconds for the log to become nonempty."""
    import os
    start = time.time()
    while time.time() - start < timeout:
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                if f.read().strip():
                    return
        time.sleep(poll_interval)
    raise AssertionError(f"Log file {log_file} did not become nonempty within {timeout} seconds.")
