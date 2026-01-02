import time
import pytest
from tests.fixtures.process_utils import _gather_leftover_entries, _kill_untracked


@pytest.fixture(scope="session", autouse=True)
def cleanup_leftover_servers():
    """Session-scoped autouse fixture that ensures no mcp-grok-server processes
    remain after the test session. It will kill any remaining untracked servers
    except a server listening on port 8000 (left alone). If any non-8000 untracked
    servers remain after this, the fixture raises an exception to fail the test run
    so leaks are fixed instead of silently ignored.
    """
    yield
    from mcp_grok.server_daemon import cleanup_leftover_servers as cleanup_daemon
    cleanup_daemon()
    # Since ServerManager is removed, no tracked servers to stop
    leftover_entries = _gather_leftover_entries()
    killed, not_killed = _kill_untracked(leftover_entries, set())
    time.sleep(0.5)
    # Recheck for remaining
    remaining_entries = _gather_leftover_entries()
    remaining = []
    for pid, name, cmdline, listen_ports in remaining_entries:
        if pid and 8000 not in listen_ports:
            remaining.append((pid, name, cmdline, listen_ports))
    if remaining:
        details = []
        for pid, name, cmdline, listen_ports in remaining:
            details.append(f"{pid}: {name} {cmdline} listening={sorted(list(listen_ports))}")
        raise RuntimeError("Leftover untracked mcp-grok-server processes after cleanup (non-8000):\n" + "\n".join(details))
