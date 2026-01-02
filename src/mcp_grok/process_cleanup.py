import os
import signal
import subprocess
from typing import List, Tuple, Optional, Set


def _gather_with_psutil() -> List[Tuple[Optional[int], str, str, Set[int]]]:
    """Gather mcp-grok-server processes using psutil."""
    entries = []
    import psutil
    for p in psutil.process_iter():
        try:
            pid = getattr(p, 'pid', None) or p.pid
            name = (p.name() or '').lower()
            cmdline = ' '.join(p.cmdline() or []).lower()
            if 'mcp-grok-server' in name or 'mcp-grok-server' in cmdline or 'mcp_grok.mcp_grok_server' in cmdline:
                listen_ports = set()
                try:
                    for c in p.net_connections(kind='inet'):
                        if c.status == psutil.CONN_LISTEN and c.laddr:
                            listen_ports.add(c.laddr[1])
                except Exception:
                    pass
                entries.append((pid, name, cmdline, listen_ports))
        except Exception:
            pass
    return entries


def _gather_with_shell() -> List[Tuple[Optional[int], str, str, Set[int]]]:
    """Gather mcp-grok-server processes using shell commands."""
    entries = []
    try:
        out = subprocess.run(['pgrep', '-af', 'mcp-grok-server'], capture_output=True, text=True)
        for line in out.stdout.splitlines():
            if line.strip():
                parts = line.strip().split(None, 1)
                pid = int(parts[0])
                cmdline = parts[1] if len(parts) > 1 else ''
                entries.append((pid, '', cmdline, set()))
    except Exception:
        pass
    return entries


def _get_listen_ports(p):
    """Get listen ports for a psutil process."""
    listen_ports = set()
    try:
        for c in p.net_connections(kind='inet'):
            if c.status == p._ps.CONN_LISTEN and c.laddr:
                listen_ports.add(c.laddr[1])
    except Exception:
        pass
    return listen_ports


def _get_process_info(p, errors):
    """Get process info with error handling."""
    pid = getattr(p, 'pid', None)
    name = ''
    try:
        name = getattr(p, '_name', '')
    except Exception:
        name = '<name unavailable>'
    cmdline = ''
    try:
        cmdline = ' '.join(p.cmdline() or [])
    except Exception:
        cmdline = '<cmdline unavailable>'
    return pid, name, cmdline


def _process_psutil_entry(p, patterns, entries, errors):
    """Process a single psutil process entry."""
    pid, name, cmdline = _get_process_info(p, errors)
    try:
        if any(pat in (name or '').lower() or pat in cmdline.lower() for pat in patterns):
            listen_ports = _get_listen_ports(p)
            entries.append((pid, name, cmdline, listen_ports))
    except Exception as e:  # psutil exceptions
        errors.append(f"Error processing process {pid} ({name}, cmdline: {cmdline}): {e}")


def _gather_running_processes(
    patterns: List[str]
) -> List[Tuple[Optional[int], str, str, Set[int]]]:
    """Gather entries of leftover processes matching any of the patterns."""
    entries = []
    errors = []
    try:
        import psutil
        for p in psutil.process_iter():
            _process_psutil_entry(p, patterns, entries, errors)
    except ImportError:
        # Fallback to shell
        pgrep_patterns = '|'.join(patterns)
        out = subprocess.run(['pgrep', '-af', pgrep_patterns], capture_output=True, text=True)
        for line in out.stdout.splitlines():
            if line.strip():
                parts = line.strip().split(None, 1)
                pid = int(parts[0])
                cmdline = parts[1] if len(parts) > 1 else ''
                entries.append((pid, '', cmdline, set()))
    if errors:
        raise Exception(f"Errors during process gathering: {'; '.join(errors)}")
    return entries


def _gather_running_mcp_server_processes() -> List[Tuple[Optional[int], str, str, Set[int]]]:
    """Gather entries of leftover mcp-grok-server processes."""
    return _gather_running_processes(['mcp-grok-server', 'mcp_grok.mcp_grok_server'])


def _kill_untracked(leftover_entries: List[Tuple[Optional[int], str, str, Set[int]]],
                    tracked_pids: Set[int]) -> Tuple[List, List]:
    """Kill untracked mcp-grok-server processes, except those on port 8000."""
    killed = []
    not_killed = []
    for pid, name, cmdline, listen_ports in leftover_entries:
        if pid in tracked_pids:
            continue
        if 8000 in listen_ports:
            not_killed.append((pid, name, cmdline, listen_ports))
            continue
        if pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append((pid, name, cmdline, listen_ports))
            except Exception:
                not_killed.append((pid, name, cmdline, listen_ports))
    return killed, not_killed


def cleanup_running_mcp_server_processes():
    """Clean up leftover mcp-grok-server processes not managed by the daemon."""
    tracked_pids = set()  # Assuming no tracked for daemon, or pass from ServerDaemon
    leftover_entries = _gather_running_mcp_server_processes()
    killed, not_killed = _kill_untracked(leftover_entries, tracked_pids)
    if killed:
        print(f"Cleaned up {len(killed)} leftover mcp-grok-server processes.")
    if not_killed:
        print(f"Left {len(not_killed)} processes untouched (e.g., on port 8000).")


def _gather_running_daemons() -> List[Tuple[Optional[int], str, str, Set[int]]]:
    """Gather entries of leftover mcp-grok-daemon processes."""
    return _gather_running_processes(['mcp-grok-daemon', 'mcp_grok.server_daemon'])


def cleanup_running_daemons():
    """Clean up leftover mcp-grok-daemon processes."""
    leftover_entries = _gather_running_daemons()
    killed = []
    not_killed = []
    for pid, name, cmdline, listen_ports in leftover_entries:
        if pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)
                killed.append((pid, name, cmdline, listen_ports))
            except Exception:
                not_killed.append((pid, name, cmdline, listen_ports))
    if killed:
        print(f"Cleaned up {len(killed)} leftover mcp-grok-daemon processes.")
    if not_killed:
        print(f"Could not kill {len(not_killed)} processes.")
