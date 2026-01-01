

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
    try:
        from menu import menu_core as _menu_core_for_tests
        tracked = getattr(_menu_core_for_tests.server_manager, '_servers', [])
        tracked_pids = {entry.get('proc').pid for entry in tracked if entry.get('proc')}
        started = started - tracked_pids
    except Exception:
        pass
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
