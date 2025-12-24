import os
import time
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import menu_core

def clean_log(log_file):
    try:
        os.remove(log_file)
    except OSError:
        pass

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

def test_server_log():
    clean_log(menu_core.MCP_LOGFILE)
    TEST_PORT = 8099
    proc = menu_core.server_manager.start_server(port=TEST_PORT)
    try:
        # If proc is None, server is already running; just check log exists and is nonempty
        if proc is None:
            if not os.path.exists(menu_core.MCP_LOGFILE):
                import pytest
                pytest.fail("Server is already running but mcp_server.log does not exist under this CWD; skipping log file check.")
            with open(menu_core.MCP_LOGFILE, "r") as f:
                assert f.read().strip(), "Log file is empty even though server is running."
        else:
            wait_for_log(menu_core.MCP_LOGFILE, timeout=10.0)  # usually instant, but waits up to 10s
    finally:
        if proc is not None:
            menu_core.server_manager.stop_server()
    print("PASS: MCP Server log not empty.")

def test_proxy_log():
    clean_log(menu_core.PROXY_LOGFILE)
    proc = menu_core.start_proxy()
    try:
        wait_for_log(menu_core.PROXY_LOGFILE, timeout=30.0)
    finally:
        menu_core.stop_proxy(proc)
    print("PASS: Proxy log not empty.")

def test_clear_mcp_log():
    # Write something, then clear
    with open(menu_core.MCP_LOGFILE, 'w') as f:
        f.write('some text\n')
    menu_core.clear_log(menu_core.MCP_LOGFILE)
    with open(menu_core.MCP_LOGFILE, 'r') as f:
        assert f.read() == '', "MCP log not cleared"
    print("PASS: MCP Server log cleared.")

def test_clear_proxy_log():
    # Write something, then clear
    with open(menu_core.PROXY_LOGFILE, 'w') as f:
        f.write('other text\n')
    menu_core.clear_log(menu_core.PROXY_LOGFILE)
    with open(menu_core.PROXY_LOGFILE, 'r') as f:
        assert f.read() == '', "Proxy log not cleared"
    print("PASS: Proxy log cleared.")

def test_proxy_log_config_error():
    # Remove previous log and start proxy
    try:
        os.remove(menu_core.PROXY_LOGFILE)
    except OSError:
        pass
    proc = menu_core.start_proxy()
    try:
        start = time.time()
        error_found = False
        while time.time() - start < 10:
            if os.path.exists(menu_core.PROXY_LOGFILE):
                with open(menu_core.PROXY_LOGFILE, "r") as f:
                    text = f.read()
                    if "Failed to load config" in text or "Error: Invalid config format" in text:
                        error_found = True
                        break
            time.sleep(0.3)
        assert not error_found, "Proxy log reports a config loading error!"
    finally:
        menu_core.stop_proxy(proc)

def test_start_server_runs_and_stops():
    """Test start_server launches a server process that stays running and can be stopped, or confirms an existing server."""
    TEST_PORT = 8099
    proc = menu_core.server_manager.start_server(port=TEST_PORT)
    assert proc is not None, "start_server did not return a process object"
    try:
        # Give the process a brief moment to start
        time.sleep(1)
        assert proc.poll() is None, "Server process exited prematurely after start"
    finally:
        menu_core.server_manager.stop_server()
        assert proc.poll() is not None, "Server process did not stop after stop_server called"
