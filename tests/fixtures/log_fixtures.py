import os
import pytest
from mcp_grok.config import config

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
