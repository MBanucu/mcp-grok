class DaemonManager:
    def __init__(self):
        self.initial_daemons = set()

    def set_initial(self):
        from mcp_grok.server_daemon import _gather_running_daemons
        self.initial_daemons = {pid for pid, _, _, _ in _gather_running_daemons() if pid is not None}

    def cleanup(self):
        from mcp_grok.server_daemon import _gather_running_daemons, cleanup_running_daemons
        final_daemons = {pid for pid, _, _, _ in _gather_running_daemons() if pid is not None}
        extra_daemons = final_daemons - self.initial_daemons
        if extra_daemons:
            cleanup_running_daemons()
            # Check again after cleanup
            final_daemons_after = {pid for pid, _, _, _ in _gather_running_daemons() if pid is not None}
            extra_daemons_after = final_daemons_after - self.initial_daemons
            if extra_daemons_after:
                raise RuntimeError(f"Daemons left running after cleanup: {extra_daemons_after}")


_daemon_manager = DaemonManager()
