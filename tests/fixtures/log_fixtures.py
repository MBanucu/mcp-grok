import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_log_dirs():
    """Ensure parent directories for configured log files exist for tests."""
    try:
        os.makedirs(os.path.expanduser('~/.mcp-grok'), exist_ok=True)
    except Exception:
        pass
