

_test_proc_before = {}
_test_leaks = []


def pytest_runtest_setup(item):
    from tests.fixtures.process_utils import _find_mcp_procs
    _test_proc_before[item.nodeid] = set(_find_mcp_procs().keys())


def _get_tracked_server_pids():
    import psutil
    import urllib.request
    import json
    tracked = set()
    for proc in psutil.process_iter():
        try:
            cmd = ' '.join(proc.cmdline() or [])
            if 'mcp_grok.server_daemon' in cmd:
                port = None
                args = proc.cmdline()
                for i in range(len(args) - 1):
                    if args[i] == '--port':
                        port = int(args[i + 1])
                        break
                if port:
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/list", timeout=1) as r:
                            data = json.load(r)
                            tracked.update(int(p) for p in data.get('servers', {}))
                    except Exception:
                        pass
        except psutil.NoSuchProcess:
            pass
    return tracked


def pytest_runtest_teardown(item, nextitem):
    from tests.fixtures.process_utils import _find_mcp_procs
    before = _test_proc_before.get(item.nodeid, set())
    after = set(_find_mcp_procs().keys())
    started = after - before
    # Exclude servers managed by running daemons
    tracked_pids = _get_tracked_server_pids()
    started = started - tracked_pids
    if started:
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
        lines = [
            "Detected tests that started mcp-grok-server processes and did not stop them:"]
        for nodeid, details in _test_leaks:
            lines.append(f"- {nodeid}")
            for d in details:
                lines.append(f"    {d}")
        print("\n" + "\n".join(lines) + "\n")
