

_test_proc_before = {}
_test_leaks = []


def pytest_runtest_setup(item):
    from tests.fixtures.process_utils import _find_mcp_procs
    _test_proc_before[item.nodeid] = set(_find_mcp_procs().keys())


def pytest_runtest_teardown(item, nextitem):
    from tests.fixtures.process_utils import _find_mcp_procs
    before = _test_proc_before.get(item.nodeid, set())
    after = set(_find_mcp_procs().keys())
    started = after - before
    # Exclude servers managed by running daemons
    import psutil
    import urllib.request
    import json
    tracked_pids = set()
    try:
        daemons = psutil.process_iter(attrs=['pid', 'cmdline'])
        for p in daemons:
            try:
                cmdline = p.info['cmdline'] or []
                if 'mcp_grok.server_daemon' in ' '.join(cmdline):
                    for i, arg in enumerate(cmdline):
                        if arg == '--port' and i + 1 < len(cmdline):
                            port = int(cmdline[i+1])
                            url = f"http://127.0.0.1:{port}/list"
                            with urllib.request.urlopen(url, timeout=1) as resp:
                                data = json.load(resp)
                                servers = data.get('servers', {})
                                tracked_pids.update(int(pid) for pid in servers.keys())
            except Exception:
                pass
    except Exception:
        pass
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
