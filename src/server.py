import logging
import subprocess
import os
import threading
import time
import dataclasses
from dataclasses import dataclass
from typing import List
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from mcp.types import ToolAnnotations

# --- CONFIGURATION ---
import getpass


@dataclass
class Config:
    projects_dir: str = os.path.expanduser('~/dev/mcp-projects')
    shell_user: str = getpass.getuser()
    shell_cmd: List[str] = dataclasses.field(
        default_factory=lambda: [
            'sudo', '-u', getpass.getuser(), '--login', 'bash', '-l'
        ]
    )
    log_file: str = 'server_audit.log'
    port: int = 8000
    default_project: str = 'default'


config = Config()

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(config.log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- SESSION SHELL MANAGEMENT ---


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
                logger.error(f"Exception in start_shell (cwd={cwd}): {type(e).__name__}: {e}", exc_info=True)
                return f"Error: Could not start shell: {type(e).__name__}: {str(e)}\nSee server log for details."
            self._shell = proc
            pid = getattr(proc, 'pid', None)
            poll_status = proc.poll()
            logger.info("Started clean shell in %r with PID=%s, initial poll()=%s", cwd, pid, poll_status)
            if poll_status is not None:
                logger.warning(
                    f"Shell process for {cwd!r} exited immediately with poll()={poll_status!r}, "
                    f"returncode={proc.returncode!r}")
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
            return None, None, "Session shell communication pipe is not available."
        stdin = getattr(proc, 'stdin', None)
        stdout = getattr(proc, 'stdout', None)
        if stdin is None or stdout is None:
            return None, None, "Session shell communication pipe is not available."
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
                    "Session shell not active when attempting to execute command. "
                    "_shell=%r, _cwd=%r, poll=%r",
                    self._shell, self._cwd, getattr(self._shell, 'poll', lambda: None)() if self._shell else None
                )
                return "Error: No session shell active. You must create or activate a project first."
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
                out = out[:8192] + "\n...[output truncated]..."  # Truncate long output
            logger.info(
                "SessionShell[dir=%s] cmd %r output %d bytes",
                self._cwd, command, len(out)
            )
            return out


shell_manager = ShellManager(config)

# --- PROJECT MANAGEMENT HELPERS ---


def safe_project_name(name: str) -> bool:
    import re
    return re.match(r'^[a-zA-Z0-9_.-]+$', name) is not None


def project_path(name: str) -> str:
    return os.path.join(config.projects_dir, name)


def ensure_projects_dir():
    os.makedirs(config.projects_dir, exist_ok=True)

# --- MCP SERVER SETUP ---


mcp = FastMCP(
    "ConsoleAccessServer",
    instructions="Console tool. Run shell commands in persistent project shells.",
    stateless_http=True,
    json_response=True,
)


class ActiveProjectInfo(BaseModel):
    name: str
    path: str


@mcp.tool(title="Execute Any Shell Command", annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=False))
def execute_shell(command: str = "") -> str:
    """
    Execute any single shell command in the persistent shell of the active project.
    - Executes arbitrary commands via session shell.
    - max output: 8KB.
    - Timeout: 180s.
    """
    if not command.strip():
        return "Error: Command cannot be empty."
    return shell_manager.execute(command)


@mcp.tool(title="Get Active Project")
def get_active_project() -> ActiveProjectInfo:
    """
    Returns info about the currently active project: both name and full path.
    """
    cwd = shell_manager.cwd
    name = os.path.basename(cwd) if cwd and os.path.isdir(cwd) else ""
    path = cwd if cwd and os.path.isdir(cwd) else ""
    return ActiveProjectInfo(name=name, path=path)


@mcp.tool(title="List All Projects")
def list_all_projects() -> list:
    """
    Returns a sorted list of all project directories in ~/dev/mcp-projects.
    """
    ensure_projects_dir()
    return sorted([
        name for name in os.listdir(config.projects_dir)
        if os.path.isdir(os.path.join(config.projects_dir, name))
    ])


@mcp.tool(title="Create New Project")
def create_new_project(project_name: str) -> str:
    """
    Creates a new project directory under ~/dev/mcp-projects/<project_name> and starts a persistent shell in that directory.
    """
    if not safe_project_name(project_name):
        return "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
    ensure_projects_dir()
    proj_path = project_path(project_name)
    if not os.path.exists(proj_path):
        os.makedirs(proj_path, exist_ok=True)
    shell_manager.stop_shell()
    return shell_manager.start_shell(proj_path)


@mcp.tool(title="Change Active Project")
def change_active_project(project_name: str) -> str:
    """
    Switch to an existing project under ~/dev/mcp-projects/<project_name> and start a persistent shell in that directory.
    Does NOT create the directory. Kills previous shell if running and starts new shell in the project dir.
    """
    if not safe_project_name(project_name):
        return "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
    proj_path = project_path(project_name)
    if not os.path.isdir(proj_path):
        return (
            "Error: Project directory does not exist: {}".format(proj_path)
        )
    shell_manager.stop_shell()
    return shell_manager.start_shell(proj_path)

# --- ENTRY POINT ---


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000, help='Port to run MCP server on')
    parser.add_argument(
        '--projects-dir', type=str, default=config.projects_dir, help='Base directory for MCP projects'
    )
    parser.add_argument(
        '--default-project', type=str, default=config.default_project,
        help='Name for the default project to activate on server start'
    )
    args = parser.parse_args()
    config.port = args.port
    config.projects_dir = os.path.expanduser(args.projects_dir)
    config.default_project = args.default_project
    ensure_projects_dir()
    default_proj_path = project_path(config.default_project)
    if not os.path.exists(default_proj_path):
        logger.info(
            "Server startup: default project '%s' does not exist. "
            "Creating new project.",
            config.default_project
        )
        result = create_new_project(config.default_project)
        logger.info(
            "Default project creation result: %s",
            result)

    else:
        logger.info(
            "Server startup: default project '%s' exists. "
            "Activating.",
            config.default_project
        )
        result = change_active_project(config.default_project)
        logger.info(
            "Default project activation result: %s",
            result)

    mcp.settings.port = config.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
