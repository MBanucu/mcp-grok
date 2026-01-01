import os
import subprocess
import socket

from mcp_grok.config import config


def _writable_logfile(preferred):
    logdir = os.path.dirname(preferred)
    try:
        os.makedirs(logdir, exist_ok=True)
        with open(preferred, "a"):
            pass
        return preferred
    except Exception:
        fallback = "/tmp/" + os.path.basename(preferred)
        try:
            with open(fallback, "a"):
                pass
            return fallback
        except Exception:
            raise RuntimeError(f"Unable to create log file in {preferred} or /tmp")


class ServerManager:
    def __init__(self):
        # Maintain a stack of started servers to avoid orphaning and to allow
        # stop_server() to stop the most-recently-started server (LIFO), which
        # preserves test expectations and avoids leaking processes.
        self._servers = []  # list of dicts: {port, proc, log_fd}

    def _find_running_for_port(self, port):
        for entry in self._servers:
            proc = entry.get('proc')
            if proc and proc.poll() is None and entry.get('port') == port:
                return entry
        return None

    def start_server(self, port=8000, projects_dir=None):
        # If a server is already listening on that port and we have tracked it,
        # return the tracked process. If something else is listening, return None
        try:
            with socket.create_connection(('localhost', port), timeout=2):
                entry = self._find_running_for_port(port)
                if entry is not None:
                    print(f"Server is already running (started by this process) on port {port}.")
                    return entry['proc']
                print(f"Server is already running on port {port}.")
                return None
        except (ConnectionRefusedError, OSError):
            # Port free
            pass

        # Start a new server process and push it onto the stack
        log_fd = open(_writable_logfile(os.path.expanduser(
            f'~/.mcp-grok/{config.log_timestamp}_{config.port}_mcp-shell.log')), "a")
        cmd = ['mcp-grok-server', '--port', str(port)]
        if projects_dir:
            cmd.extend(['--projects-dir', projects_dir])
        proc = subprocess.Popen(
            cmd,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            env={**os.environ, 'NO_COLOR': '1'},
        )
        self._servers.append({'port': port, 'proc': proc, 'log_fd': log_fd})
        return proc

    def _pop_entry(self, proc=None, port=None):
        # Pop and return a matching server entry. Search LIFO so latest starts take precedence.
        if proc is None and port is None:
            if not self._servers:
                return None
            return self._servers.pop()
        for i in range(len(self._servers) - 1, -1, -1):
            entry = self._servers[i]
            if proc is not None and entry.get('proc') is proc:
                return self._servers.pop(i)
            if port is not None and entry.get('port') == port:
                return self._servers.pop(i)
        return None

    def stop_server(self, proc=None, port=None):
        """
        Stop a running server.
        - If `proc` is provided, stop the matching process if tracked.
        - Else if `port` is provided, stop the most-recently-started server for that port.
        - Else stop the most-recently-started server (LIFO).
        """
        entry = self._pop_entry(proc=proc, port=port)
        if not entry:
            return

        proc = entry.get('proc')
        log_fd = entry.get('log_fd')
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        try:
            if log_fd:
                log_fd.close()
        except Exception:
            pass


server_manager = ServerManager()


def start_proxy():
    log = open(_writable_logfile(config.proxy_log), "a")
    proc = subprocess.Popen(
        ['superassistant-proxy'],
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        close_fds=True,
        env={**os.environ, 'NO_COLOR': '1'},
    )
    return proc


def stop_proxy(proc):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def clear_log(log_path):
    if os.path.exists(log_path):
        with open(log_path, "w"):
            pass


def log_content(log_path):
    if os.path.exists(log_path):
        with open(log_path, "r") as f:
            return f.read()
    return None
