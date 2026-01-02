from .daemon_manager import _daemon_manager
from .test_leak_tracker import TestLeakTracker

tracker = TestLeakTracker()


def pytest_runtest_setup(item):
    tracker.setup(item)


def pytest_runtest_teardown(item, nextitem):
    tracker.teardown(item, nextitem)


def pytest_sessionstart(session):
    _daemon_manager.set_initial()


def pytest_sessionfinish(session, exitstatus):
    # Check daemon cleanup
    _daemon_manager.cleanup()
    if tracker.test_leaks:
        lines = [
            "Detected tests that started mcp-grok-server processes and did not stop them:"]
        for nodeid, details in tracker.test_leaks:
            lines.append(f"- {nodeid}")
            for d in details:
                lines.append(f"    {d}")
        print("\n" + "\n".join(lines) + "\n")
