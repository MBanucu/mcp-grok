

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


import threading
import time

_initial_daemons = set()

class ProcessMonitor:
    def __init__(self):
        self.history = []
        self.thread = None
        self.stop_event = threading.Event()
        self.started_event = threading.Event()

    def start(self):
        self.thread = threading.Thread(target=self._monitor_processes, daemon=True)
        self.thread.start()
        if self.started_event.wait(timeout=5.0):
            print("Monitoring confirmed started", flush=True)
        else:
            print("Monitoring start timeout", flush=True)

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=1.0)
        self.history.append({"type": "monitoring_stopped"})

    def _monitor_processes(self):
        """Background thread to monitor process changes."""
        import psutil
        previous_pids = set()
        try:
            initial_pids = {p.pid for p in psutil.process_iter(attrs=['pid'])}
            previous_pids = initial_pids.copy()
            self.history.append({"type": "initial_processes", "count": len(initial_pids)})
            self.started_event.set()
        except Exception as e:
            self.history.append({"type": "error", "message": f"Error getting initial processes: {e}"})
            return

        process_info = {}  # pid -> (name, cmdline)
        while not self.stop_event.is_set():
            import datetime
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            try:
                current_procs = {p.pid: p for p in psutil.process_iter(attrs=['pid', 'name'])}
                current_pids = set(current_procs.keys())
                new_pids = current_pids - previous_pids
                gone_pids = previous_pids - current_pids

                # Update info for new processes
                for pid in new_pids:
                    p = current_procs.get(pid)
                    if p:
                        try:
                            name = p.name() or ''
                        except Exception:
                            name = '<unknown>'
                        try:
                            cmdline = ' '.join(p.cmdline() or [])
                        except Exception:
                            cmdline = '<unknown>'
                        process_info[pid] = (name, cmdline)

                if new_pids:
                    processes = []
                    for pid in sorted(new_pids):
                        name, cmdline = process_info.get(pid, ('<unknown>', '<unknown>'))
                        processes.append({"pid": pid, "name": name, "cmdline": cmdline})
                    self.history.append({"type": "new_processes", "processes": processes, "timestamp": timestamp})

                if gone_pids:
                    processes = []
                    for pid in sorted(gone_pids):
                        name, cmdline = process_info.get(pid, ('<unknown>', '<unknown>'))
                        processes.append({"pid": pid, "name": name, "cmdline": cmdline})
                    self.history.append({"type": "terminated_processes", "processes": processes, "timestamp": timestamp})

                previous_pids = current_pids
            except Exception as e:
                self.history.append({"type": "error", "message": f"Error monitoring processes: {e}", "timestamp": timestamp})
            time.sleep(0.05)

    def print_history(self):
        if self.history:
            # First pass: collect created and terminated PIDs
            created_pids = set()
            terminated_pids = set()
            for entry in self.history:
                if isinstance(entry, dict):
                    if entry["type"] == "new_processes":
                        for proc in entry["processes"]:
                            created_pids.add(proc['pid'])
                    elif entry["type"] == "terminated_processes":
                        for proc in entry["processes"]:
                            terminated_pids.add(proc['pid'])

            not_terminated = created_pids - terminated_pids

            # Second pass: print with highlighting
            print("\nProcess lifecycle history:")
            for entry in self.history:
                if isinstance(entry, dict):
                    if entry["type"] == "initial_processes":
                        print(f"  Initial processes: {entry['count']}")
                    elif entry["type"] == "new_processes":
                        print(f"  [{entry['timestamp']}] New processes:")
                        for proc in entry["processes"]:
                            pid = proc['pid']
                            created_pids.add(pid)
                            if pid in not_terminated:
                                print(f"    \033[91m=====> LEAK: PID {proc['pid']}: {proc['name']} - {proc['cmdline']}\033[0m")
                            else:
                                print(f"    PID {proc['pid']}: {proc['name']} - {proc['cmdline']}")
                    elif entry["type"] == "terminated_processes":
                        print(f"  [{entry['timestamp']}] Terminated processes:")
                        for proc in entry["processes"]:
                            print(f"    PID {proc['pid']}: {proc['name']} - {proc['cmdline']}")
                    elif entry["type"] == "error":
                        print(f"  [{entry.get('timestamp', 'N/A')}] {entry['message']}")
                    elif entry["type"] == "monitoring_stopped":
                        print("  Monitoring stopped")
                    else:
                        print(f"  Unknown entry: {entry}")
                else:
                    print(f"  {entry}")

            # Print summary
            if not_terminated:
                print(f"\nProcesses created during session but not terminated: {sorted(not_terminated)}")
            else:
                print("\nAll created processes were properly terminated.")
            print()

_monitor = ProcessMonitor()

def pytest_sessionstart(session):
    print("pytest_sessionstart called", flush=True)
    from mcp_grok.server_daemon import _gather_leftover_daemons
    global _initial_daemons, _monitor
    _initial_daemons = {pid for pid, _, _, _ in _gather_leftover_daemons() if pid is not None}
    # Start process monitoring
    _monitor.start()


def pytest_sessionfinish(session, exitstatus):
    # Stop process monitoring
    global _monitor
    _monitor.stop()

    # Print process history
    _monitor.print_history()

    # Check daemon cleanup
    from mcp_grok.server_daemon import _gather_leftover_daemons, cleanup_leftover_daemons
    final_daemons = {pid for pid, _, _, _ in _gather_leftover_daemons() if pid is not None}
    extra_daemons = final_daemons - _initial_daemons
    if extra_daemons:
        cleanup_leftover_daemons()
        # Check again after cleanup
        final_daemons_after = {pid for pid, _, _, _ in _gather_leftover_daemons() if pid is not None}
        extra_daemons_after = final_daemons_after - _initial_daemons
        if extra_daemons_after:
            raise RuntimeError(f"Daemons left running after cleanup: {extra_daemons_after}")
    if _test_leaks:
        lines = [
            "Detected tests that started mcp-grok-server processes and did not stop them:"]
        for nodeid, details in _test_leaks:
            lines.append(f"- {nodeid}")
            for d in details:
                lines.append(f"    {d}")
        print("\n" + "\n".join(lines) + "\n")
