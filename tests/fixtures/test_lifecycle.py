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
    tracker.report_leaks()
