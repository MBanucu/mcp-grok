import pytest
from tests.fixtures.server_fixtures import server_daemon_proc, mcp_server  # noqa: F401
from tests.fixtures.log_fixtures import ensure_log_dirs  # noqa: F401
from tests.fixtures.cleanup import cleanup_leftover_servers  # noqa: F401
from tests.fixtures.test_lifecycle import (  # noqa: F401
    pytest_runtest_setup,
    pytest_runtest_teardown,
    pytest_sessionfinish,
)
from mcp_grok.server_daemon import _gather_leftover_daemons


@pytest.fixture(scope="session", autouse=True)
def check_daemon_cleanup():
    """Session fixture to ensure no daemons are left running after tests."""
    initial_daemons = {pid for pid, _, _, _ in _gather_leftover_daemons() if pid is not None}
    yield
    # Check again
    final_daemons = {pid for pid, _, _, _ in _gather_leftover_daemons() if pid is not None}
    extra_daemons = final_daemons - initial_daemons
    from mcp_grok.server_daemon import cleanup_leftover_daemons
    cleanup_leftover_daemons()
    if extra_daemons:
        raise RuntimeError(f"Daemons left running after cleanup: {extra_daemons}")
