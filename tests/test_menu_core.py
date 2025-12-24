import os
import time
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import menu_core

def clean_log(log_file):
    try: os.remove(log_file)
    except OSError: pass

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
    proc = menu_core.start_server()
    try:
        wait_for_log(menu_core.MCP_LOGFILE, timeout=10.0)  # usually instant, but waits up to 10s
    finally:
        menu_core.stop_server(proc)
    print("PASS: MCP Server log not empty.")

def test_proxy_log():
    clean_log(menu_core.PROXY_LOGFILE)
    proc = menu_core.start_proxy()
    try:
        wait_for_log(menu_core.PROXY_LOGFILE, timeout=30.0)
    finally:
        menu_core.stop_proxy(proc)
    print("PASS: Proxy log not empty.")
