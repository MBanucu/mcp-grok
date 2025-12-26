import subprocess
import threading
import time
import logging
from .config import Config


logger = logging.getLogger(__name__)


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
                    bufsize=1
                )
                # Ensure login shell is in correct directory
                if proc.stdin is not None:
                    proc.stdin.write(f'cd "{cwd}"\n')
                    proc.stdin.flush()
            except Exception as e:
                logger.error(
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
            logger.info(
                "Started clean shell in %r with PID=%s, initial poll()=%s",
                cwd,
                pid,
                poll_status
            )
            if poll_status is not None:
                logger.warning(
                    f"Shell process for {cwd!r} exited immediately with "
                    f"poll()={poll_status!r}, returncode={proc.returncode!r}"
                )
            return f"Started shell for project: {cwd}"

    def stop_shell(self):
        with self._shell_lock:
            if self._shell is not None and self._shell.poll() is None:
                self._shell.kill()
            self._shell = None
            self._cwd = None
            logger.info("Stopped shell")

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
            if time.time() - t0 > 180:
                return None, "Error: Shell command timed out."
        return "".join(out_lines).strip(), None

    def execute(self, command: str) -> str:
        with self._shell_lock:
            if not self.is_active():
                logger.error(
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
            logger.info(
                "SessionShell[dir=%s] cmd %r output %d bytes",
                self._cwd, command, len(out)
            )
            return out
