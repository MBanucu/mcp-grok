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
    # Prefer using the ServerManager API to start and track the fixture server.
    # Falls back to the legacy helper if the in-process server_manager isn't importable.
    server_proc = None
    try:
        from menu import menu_core
        try:
            server_proc = menu_core.server_manager.start_server(port=PORT, projects_dir=DEV_ROOT)
        except Exception:
            server_proc = None
    except Exception:
        server_proc = None

    if server_proc is None:
        # fallback: start process directly
        server_proc = start_mcp_server()
    wait_for_mcp_server(server_proc)

    yield f"http://localhost:{PORT}/mcp"

    # Teardown: prefer server_manager stop if possible, else the legacy teardown
    try:
        from menu import menu_core
        try:
            menu_core.server_manager.stop_server(proc=server_proc)
        except Exception:
            teardown_mcp_server(server_proc)
    except Exception:
        teardown_mcp_server(server_proc)


@pytest.fixture(scope="session", autouse=True)
def cleanup_leftover_servers():
    """Session-scoped autouse fixture that ensures no mcp-grok-server processes
    remain after the test session. It will stop tracked servers, then kill any
    remaining untracked servers except a server listening on port 8000 (left alone).
    If any non-8000 untracked servers remain after this, the fixture raises an
    exception to fail the test run so leaks are fixed instead of silently ignored.
    """
    # Run tests
    yield

    # 1) Ask the in-process server_manager to stop tracked servers
    tracked_pids = set()
    tracked_ports = set()
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
                    if pid:
                        tracked_pids.add(pid)
                    if port is not None:
                        tracked_ports.add(port)
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
    leftover_entries = []  # tuples (pid, name, cmdline, listen_ports)
    try:
        import psutil
        for p in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = p.info.get('pid')
                name = (p.info.get('name') or '').lower()
                cmdline = ' '.join(p.info.get('cmdline') or []).lower()
                if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                    listen_ports = set()
                    try:
                        for c in p.connections(kind='inet'):
                            # consider only listening sockets
                            if c.status == psutil.CONN_LISTEN:
                                if c.laddr and isinstance(c.laddr, tuple):
                                    listen_ports.add(c.laddr[1])
                    except Exception:
                        # ignore connection inspection errors
                        pass
                    leftover_entries.append((pid, name, cmdline, listen_ports))
            except Exception:
                pass
    except Exception:
        # Fallback: use shell tools to find processes (limited info)
        try:
            import shutil
            if shutil.which('pgrep'):
                out = subprocess.run(['pgrep', '-af', 'mcp-grok-server'], capture_output=True, text=True)
                for line in out.stdout.splitlines():
                    if line.strip():
                        parts = line.strip().split(None, 1)
                        pid = int(parts[0])
                        cmdline = parts[1] if len(parts) > 1 else ''
                        leftover_entries.append((pid, '', cmdline, set()))
            else:
                out = subprocess.run(['ps', '-ef'], capture_output=True, text=True)
                for line in out.stdout.splitlines():
                    if 'mcp-grok-server' in line or 'mcp_grok.mcp_grok_server' in line:
                        leftover_entries.append((None, '', line.strip(), set()))
        except Exception:
            pass

    # 3) Kill untracked leftover servers, except those listening on port 8000
    killed = []
    not_killed = []
    for pid, name, cmdline, listen_ports in leftover_entries:
        if pid in tracked_pids:
            # tracked by server_manager; was already asked to stop
            continue
        if 8000 in listen_ports:
            # preserve server on port 8000
            not_killed.append((pid, name, cmdline, listen_ports))
            continue
        # attempt to terminate the untracked process
        try:
            if pid is not None:
                # prefer psutil termination if available
                try:
                    import psutil as _ps
                    proc = _ps.Process(pid)
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except Exception:
                        proc.kill()
                    killed.append((pid, name, cmdline, listen_ports))
                    continue
                except Exception:
                    # fallback to os.kill
                    import os
                    import signal
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except Exception:
                        pass
            killed.append((pid, name, cmdline, listen_ports))
        except Exception:
            # record failure to kill
            not_killed.append((pid, name, cmdline, listen_ports))

    # small pause to let terminations settle
    time.sleep(0.5)

    # 4) Re-check for any remaining untracked (non-8000) leftover processes
    remaining = []
    try:
        import psutil as _ps2
        for p in _ps2.process_iter(['pid', 'name', 'cmdline']):
            try:
                pid = p.info.get('pid')
                name = (p.info.get('name') or '').lower()
                cmdline = ' '.join(p.info.get('cmdline') or []).lower()
                if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                    if pid in tracked_pids:
                        continue
                    # get listen ports
                    listen_ports = set()
                    try:
                        for c in p.connections(kind='inet'):
                            if c.status == _ps2.CONN_LISTEN and c.laddr and isinstance(c.laddr, tuple):
                                listen_ports.add(c.laddr[1])
                    except Exception:
                        pass
                    if 8000 in listen_ports:
                        continue
                    remaining.append((pid, name, cmdline, listen_ports))
            except Exception:
                pass
    except Exception:
        # Without psutil do a best-effort ps check
        out = subprocess.run(['ps', '-ef'], capture_output=True, text=True)
        for line in out.stdout.splitlines():
            if 'mcp-grok-server' in line or 'mcp_grok.mcp_grok_server' in line:
                parts = line.strip().split(None, 1)
                try:
                    pid = int(parts[0])
                except Exception:
                    pid = None
                if pid in tracked_pids:
                    continue
                remaining.append((pid, '', line.strip(), set()))

        if remaining:
            details = []
            for pid, name, cmdline, listen_ports in remaining:
                details.append("%s: %s %s listening=%s" % (pid, name, cmdline, sorted(list(listen_ports))))
            raise RuntimeError("Leftover untracked mcp-grok-server processes after cleanup (non-8000):\n" + "\n".join(details))


    # Optionally print summary of actions
    if killed:
        print("\nKilled untracked mcp-grok-server processes:")
        for pid, name, cmdline, listen_ports in killed:
            print(f" - {pid}: {name} {cmdline} listening={sorted(list(listen_ports))}")
    if not_killed:
        print("\nLeft untracked mcp-grok-server processes (preserved, e.g. port 8000):")
        for pid, name, cmdline, listen_ports in not_killed:
            print(f" - {pid}: {name} {cmdline} listening={sorted(list(listen_ports))}")


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

    # Exclude processes that are intentionally tracked by module/session fixtures
    try:
        from menu import menu_core as _menu_core_for_tests
        tracked = getattr(_menu_core_for_tests.server_manager, '_servers', [])
        tracked_pids = {entry.get('proc').pid for entry in tracked if entry.get('proc')}
        started = started - tracked_pids
    except Exception:
        # If we can't access the in-process server manager, continue as before
        pass


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
