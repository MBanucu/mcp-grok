import os
import sys
import time
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import menu_core

def test_proxy_log_config_error():
    # Remove previous log and start proxy
    try: os.remove(menu_core.PROXY_LOGFILE)
    except OSError: pass
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
