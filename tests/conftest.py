import os
import shutil
import subprocess
import time
import socket
import pytest

from mcp_grok.config import config


def pick_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


PORT = pick_free_port()
DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")


def setup_project_dir():
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT)
    os.makedirs(DEV_ROOT, exist_ok=True)


def start_mcp_server():
    return subprocess.Popen([
        "mcp-grok-server", "--port", str(PORT), "--projects-dir", DEV_ROOT
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def wait_for_mcp_server(server_proc, timeout=30):
    start_time = time.time()
    output_lines = []
    while True:
        if server_proc.poll() is not None:
            # Server crashed, print all output that was produced
            if server_proc.stdout is not None:
                more_output = server_proc.stdout.read()
                if more_output:
                    output_lines.append(more_output)
            output = "".join(output_lines)
            print("\n[SERVER STARTUP FAILED] Full server output:\n" + output)
            raise RuntimeError("Server process exited prematurely. See server logs above for reason.")
        if server_proc.stdout is not None:
            line = server_proc.stdout.readline()
            if line:
                output_lines.append(line)
            if "Uvicorn running on http://" in line:
                break
        else:
            time.sleep(0.1)
        if time.time() - start_time > timeout:
            output = "".join(output_lines)
            print("\n[SERVER STARTUP TIMEOUT] Full server output so far:\n" + output)
            raise TimeoutError("Timed out waiting for server readiness. See server logs above for reason.")


def teardown_mcp_server(server_proc):
    server_proc.terminate()
    try:
        server_proc.wait(timeout=5)
    except Exception:
        server_proc.kill()
    if getattr(server_proc, 'stdout', None):
        try:
            server_proc.stdout.close()
        except Exception:
            pass
    if os.path.exists(DEV_ROOT):
        shutil.rmtree(DEV_ROOT, ignore_errors=True)


@pytest.fixture(scope="session", autouse=True)
def ensure_log_dirs():
    """Ensure parent directories for configured log files exist for tests."""
    try:
        os.makedirs(os.path.dirname(config.mcp_shell_log), exist_ok=True)
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(config.proxy_log), exist_ok=True)
    except Exception:
        pass


@pytest.fixture(scope="session")
def mcp_server():
    setup_project_dir()
    server_proc = start_mcp_server()
    wait_for_mcp_server(server_proc)
    yield f"http://localhost:{PORT}/mcp"
    teardown_mcp_server(server_proc)


@pytest.fixture(scope="session", autouse=True)
def cleanup_leftover_servers():
    """Session-scoped autouse fixture that ensures no mcp-grok-server processes
    remain after the test session. If any are found, it raises an exception to
    fail the test run so leaks are fixed instead of silently killed.
    """
    # Run tests
    yield

    # 1) Ask the in-process server_manager to stop tracked servers
    try:
        from menu import menu_core
        sm = menu_core.server_manager
        # Print the servers that are tracked and will be stopped (port and pid if available)
        try:
            tracked = getattr(sm, '_servers', [])
            if tracked:
                print("\nServers tracked by menu_core.server_manager that will be stopped:")
                for entry in list(tracked):
                    port = entry.get('port')
                    proc = entry.get('proc')
                    pid = getattr(proc, 'pid', None) if proc is not None else None
                    cmd = None
                    try:
                        cmd = ' '.join(proc.args) if proc is not None else None
                    except Exception:
                        cmd = None
                    print(f" - port={port}, pid={pid}, cmd={cmd}")
        except Exception:
            pass
        while getattr(sm, '_servers', None):
            try:
                sm.stop_server()
            except Exception:
                break
    except Exception:
        # If menu_core isn't importable, proceed to system-level checks
        pass

    # 2) Inspect remaining processes; prefer psutil for reliable info
    leftover = []
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = (p.info.get('name') or '').lower()
                cmdline = ' '.join(p.info.get('cmdline') or []).lower()
                if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                    leftover.append(f"{p.pid}: {name} {cmdline}")
            except Exception:
                pass
    except Exception:
        # Fallback: use shell tools to find processes
        try:
            import shutil
            if shutil.which('pgrep'):
                out = subprocess.run(['pgrep', '-af', 'mcp-grok-server'], capture_output=True, text=True)
                for line in out.stdout.splitlines():
                    if line.strip():
                        leftover.append(line.strip())
            else:
                out = subprocess.run(['ps', '-ef'], capture_output=True, text=True)
                for line in out.stdout.splitlines():
                    if 'mcp-grok-server' in line or 'mcp_grok.mcp_grok_server' in line:
                        leftover.append(line.strip())
        except Exception:
            pass

    # If any leftover processes found, raise an exception to fail the test run
    if leftover:
        details = "\n".join(leftover)
        raise RuntimeError(f"Leftover mcp-grok-server processes after tests:\n{details}\nPlease ensure tests clean up started servers.")


# ----------------------------
# Per-test process tracking
# ----------------------------
try:
    import psutil as _psutil
except Exception:
    _psutil = None

_test_proc_before = {}
_test_leaks = []


def _find_mcp_procs():
    procs = {}
    if _psutil:
        for p in _psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = (p.info.get('name') or '').lower()
                cmdline = ' '.join(p.info.get('cmdline') or []).lower()
                if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                    procs[p.pid] = (name, cmdline)
            except Exception:
                pass
    else:
        # Fallback: use ps
        out = subprocess.run(['ps', '-eo', 'pid,comm,args'], capture_output=True, text=True)
        for line in out.stdout.splitlines()[1:]:
            parts = line.strip().split(None, 2)
            if len(parts) >= 3:
                pid_s, comm, args = parts
                if 'mcp-grok-server' in comm or 'mcp-grok-server' in args or 'mcp_grok.mcp_grok_server' in args:
                    try:
                        pid = int(pid_s)
                        procs[pid] = (comm, args)
                    except Exception:
                        pass
    return procs


def pytest_runtest_setup(item):
    # snapshot before the test
    _test_proc_before[item.nodeid] = set(_find_mcp_procs().keys())


def pytest_runtest_teardown(item, nextitem):
    before = _test_proc_before.get(item.nodeid, set())
    after = set(_find_mcp_procs().keys())
    started = after - before
    if started:
        # any started processes still present after teardown are potential leaks
        details = []
        all_procs = _find_mcp_procs()
        for pid in started:
            info = all_procs.get(pid)
            if info:
                details.append(f"{pid}: {info[0]} {info[1]}")
        if details:
            _test_leaks.append((item.nodeid, details))


def pytest_sessionfinish(session, exitstatus):
    if _test_leaks:
        lines = ["Detected tests that started mcp-grok-server processes and did not stop them:"]
        for nodeid, details in _test_leaks:
            lines.append(f"- {nodeid}")
            for d in details:
                lines.append(f"    {d}")
        # Print the summary and leave the existing session-level leftover check to fail the run
        print("\n" + "\n".join(lines) + "\n")
