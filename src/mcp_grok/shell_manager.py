import subprocess
import threading
import time
import logging
import os
import signal
from .config import Config


class ShellManager:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self._shell = None
        self._shell_lock = threading.Lock()
        self._cwd = None

    @property
    def cwd(self):
        return self._cwd

    def is_active(self):
        return self._shell is not None and self._shell.poll() is None

    def start_shell(self, cwd: str):
        with self._shell_lock:
            if self._shell is not None and self._shell.poll() is None:
                self._shell.kill()
            self._shell = None
            self._cwd = cwd
            try:
                proc = subprocess.Popen(
                    self.cfg.shell_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=cwd,
                    text=True,
                    bufsize=1,
                    start_new_session=True  # Start in new session/process group for safe kill
                )
                # Log PGID of child to verify isolation
                try:
                    child_pgid = os.getpgid(proc.pid)
                    logging.getLogger(__name__).info(
                        f"Shell started with PID={proc.pid}, PGID={child_pgid} (cwd={cwd!r})"
                    )
                except Exception as e:
                    logging.getLogger(__name__).warning(f"Could not get PGID for shell PID={proc.pid}: {e}")
                # Ensure login shell is in correct directory
                if proc.stdin is not None:
                    proc.stdin.write(f'cd "{cwd}"\n')
                    proc.stdin.flush()
            except Exception as e:
                logging.getLogger(__name__).error(
                    "Exception in start_shell (cwd=%r): %s: %s",
                    cwd, type(e).__name__, e,
                    exc_info=True
                )
                return (
                    (
                        f"Error: Could not start shell: {type(e).__name__}: "
                        f"{str(e)}\nSee server log for details."
                    )
                )
            self._shell = proc
            pid = getattr(proc, 'pid', None)
            poll_status = proc.poll()
            logging.getLogger(__name__).info(
                "Started clean shell in %r with PID=%s, initial poll()=%s",
                cwd,
                pid,
                poll_status
            )
            if poll_status is not None:
                logging.getLogger(__name__).warning(
                    f"Shell process for {cwd!r} exited immediately with "
                    f"poll()={poll_status!r}, returncode={proc.returncode!r}"
                )
            return f"Started shell for project: {cwd}"

    def _get_shell_pgid(self):
        proc = self._shell
        if not proc:
            return None
        try:
            return os.getpgid(proc.pid)
        except Exception:
            return None

    def _send_signal(self, pgid, sig):
        proc = self._shell
        if not proc:
            logging.getLogger(__name__).warning("No shell process to signal")
            return False
        try:
            if pgid:
                os.killpg(pgid, sig)
            else:
                os.kill(proc.pid, sig)
            return True
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to send signal {sig!r}: {e!r}")
            return False

    def _wait_for_termination(self, timeout):
        proc = self._shell
        if not proc:
            return True
        try:
            proc.wait(timeout=timeout)
            logging.getLogger(__name__).info(f"Shell (pid={proc.pid}) exited gracefully after SIGTERM.")
            return True
        except Exception:
            return False

    def stop_shell(self, timeout=4):
        with self._shell_lock:
            if self._shell is not None and self._shell.poll() is None:
                # Skipping graceful 'exit' command; proceed straight to SIGTERM/SIGKILL
                pgid = self._get_shell_pgid()

                # 1) Try SIGTERM
                sent = self._send_signal(pgid, signal.SIGTERM)
                if sent:
                    logging.getLogger(__name__).info(f"Sent SIGTERM to shell (pid={self._shell.pid})")

                # 2) Wait for graceful shutdown
                if not self._wait_for_termination(timeout=timeout):
                    # 3) Escalate to SIGKILL
                    killed = self._send_signal(pgid, signal.SIGKILL)
                    if killed:
                        try:
                            self._shell.wait(timeout=1)
                            logging.getLogger(__name__).warning(f"Had to SIGKILL shell (pid={self._shell.pid}).")
                        except Exception as ke:
                            logging.getLogger(__name__).error(f"Failed to SIGKILL shell (pid={self._shell.pid}): {ke!r}")
            else:
                logging.getLogger(__name__).info("Shell was already stopped.")
            self._shell = None
            self._cwd = None
            logging.getLogger(__name__).info("Stopped shell")

    def _get_shell_pipes(self, proc):
        if not proc:
            return (
                None, None,
                "Session shell communication pipe is not available."
            )
        stdin = getattr(proc, 'stdin', None)
        stdout = getattr(proc, 'stdout', None)
        if stdin is None or stdout is None:
            return (
                None, None,
                "Session shell communication pipe is not available."
            )
        return stdin, stdout, None

    def _read_shell_output(self, stdout):
        out_lines = []
        t0 = time.time()
        while True:
            line = stdout.readline()
            if not line:
                break
            if line.rstrip() == "__MCP_END__":  # Output delimiter
                break
            out_lines.append(line)
            if time.time() - t0 > 300:
                return None, "Error: Shell command timed out."
        return "".join(out_lines).strip(), None

    def execute(self, command: str) -> str:
        with self._shell_lock:
            if not self.is_active():
                logging.getLogger(__name__).error(
                    "Session shell not active when attempting to execute "
                    "command. _shell=%r, _cwd=%r, poll=%r",
                    self._shell,
                    self._cwd,
                    getattr(self._shell, 'poll', lambda: None)()
                    if self._shell else None,
                )
                return (
                    (
                        "Error: No session shell active. "
                        "You must create or activate a project first."
                    )
                )
            proc = self._shell
            try:
                stdin, stdout, pipe_err = self._get_shell_pipes(proc)
                if pipe_err:
                    return pipe_err
                if stdin is None or stdout is None:
                    return "Session shell communication pipe is not available."
                stdin.write(command.strip() + "\n")
                stdin.write('echo __MCP_END__\n')  # MCP output delimiter
                stdin.flush()
                out, read_err = self._read_shell_output(stdout)
                if read_err:
                    return read_err
            except Exception as e:
                return f"Shell session error: {type(e).__name__}: {str(e)}"
            if not out:
                out = ""
            if len(out) > 8192:
                out = (
                    out[:8192] +
                    "\n...[output truncated]..."
                )  # Truncate long output
            logging.getLogger(__name__).info(
                "SessionShell[dir=%s] cmd %r output %d bytes",
                self._cwd, command, len(out)
            )
            return out
