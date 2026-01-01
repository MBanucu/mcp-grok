import subprocess


def _get_listen_ports_from_psutil_proc(p):
    try:
        import psutil as _ps
        ports = set()
        for c in p.connections(kind='inet'):
            if c.status == _ps.CONN_LISTEN and c.laddr and isinstance(c.laddr, tuple):
                ports.add(c.laddr[1])
        return ports
    except Exception:
        return set()


def _gather_with_psutil():
    entries = []
    import psutil

    for p in psutil.process_iter():
        try:
            pid = getattr(p, 'pid', None) or p.pid
            try:
                name = (p.name() or '').lower()
            except Exception:
                name = ''
            try:
                cmdline = ' '.join(p.cmdline() or []).lower()
            except Exception:
                cmdline = ''
            if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                listen_ports = _get_listen_ports_from_psutil_proc(p)
                entries.append((pid, name, cmdline, listen_ports))
        except Exception:
            pass
    return entries


def _gather_with_shell():
    entries = []
    try:
        import shutil
        if shutil.which('pgrep'):
            out = subprocess.run(['pgrep', '-af', 'mcp-grok-server'], capture_output=True, text=True)
            for line in out.stdout.splitlines():
                if line.strip():
                    parts = line.strip().split(None, 1)
                    pid = int(parts[0])
                    cmdline = parts[1] if len(parts) > 1 else ''
                    entries.append((pid, '', cmdline, set()))
        else:
            out = subprocess.run(['ps', '-ef'], capture_output=True, text=True)
            for line in out.stdout.splitlines():
                if 'mcp-grok-server' in line or 'mcp_grok.mcp_grok_server' in line:
                    entries.append((None, '', line.strip(), set()))
    except Exception:
        pass
    return entries


def _gather_leftover_entries():
    try:
        return _gather_with_psutil()
    except Exception:
        return _gather_with_shell()


def _terminate_pid_with_psutil(pid):
    try:
        import psutil as _ps
        proc = _ps.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        return True
    except Exception:
        return False


def _terminate_pid_with_os(pid):
    try:
        import os
        import signal
        os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False


def _kill_untracked(leftover_entries, tracked_pids):
    killed = []
    not_killed = []
    for pid, name, cmdline, listen_ports in leftover_entries:
        if pid in tracked_pids:
            continue
        if 8000 in listen_ports:
            not_killed.append((pid, name, cmdline, listen_ports))
            continue
        if pid is not None:
            if _terminate_pid_with_psutil(pid):
                killed.append((pid, name, cmdline, listen_ports))
                continue
            if _terminate_pid_with_os(pid):
                killed.append((pid, name, cmdline, listen_ports))
                continue
        not_killed.append((pid, name, cmdline, listen_ports))
    return killed, not_killed


def _find_mcp_procs_psutil():
    procs = {}
    import psutil as _ps
    for p in _ps.process_iter():
        try:
            try:
                name = (p.name() or '').lower()
            except Exception:
                name = ''
            try:
                cmdline = ' '.join(p.cmdline() or []).lower()
            except Exception:
                cmdline = ''
            if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                procs[p.pid] = (name, cmdline)
        except Exception:
            pass
    return procs


def _find_mcp_procs_ps():
    procs = {}
    out = subprocess.run(['ps', '-eo', 'pid,comm,args'], capture_output=True, text=True)
    for line in out.stdout.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) >= 3:
            pid_s, comm, args = parts
            if 'mcp-grok-server' in comm or 'mcp-grok-server' in args or 'mcp_grok.mcp_grok_server' in args:
                try:
                    pid = int(pid_s)
                    procs[pid] = (comm, args)
                except Exception:
                    pass
    return procs


def _find_mcp_procs():
    try:
        # import psutil (unused)
        return _find_mcp_procs_psutil()
    except Exception:
        return _find_mcp_procs_ps()
