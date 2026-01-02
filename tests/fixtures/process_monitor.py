import threading
import time


class ProcessMonitor:
    """
    Monitors process lifecycle during pytest sessions to detect leaks.

    Usage in pytest fixtures:
    - In pytest_sessionstart: _monitor.start()
    - In pytest_sessionfinish: _monitor.stop(); _monitor.print_history()

    The print_history method will highlight leaking processes (those created but not terminated).
    """
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
