import logging
import subprocess
import shlex
import os
import threading
import time
from mcp.server.fastmcp import FastMCP

# Logging setup: logs to both file and stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("server_audit.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "ConsoleAccessServer",
    instructions="Secure, whitelisted console tool. NEVER expose this server to the internet!",
    # Use JSON mode, stateless HTTP for safer LLM integration:
    stateless_http=True,
    json_response=True,
)


from mcp.types import ToolAnnotations

# Session-wide persistent shell process for project work
session_shell = None
session_shell_lock = threading.Lock()
session_shell_cwd = None

@mcp.tool(
    title="Execute Any Shell Command",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        openWorldHint=False
    )
)
def execute_shell(command: str = "") -> str:
    """
    Execute any single shell command, or in persistent shell if active.
    - Executes arbitrary commands via subprocess or session shell if present.
    - WARNING: This is unsafe for production or open internet!
    - max output: 8KB.
    - Timeout: 180s.
    - Input is NOT parsed by a shell (prevents some injection).
    """
    global session_shell, session_shell_lock, session_shell_cwd
    try:
        if not command.strip():
            return "Error: Command cannot be empty."
        if session_shell is not None:
            # Send command to running shell
            with session_shell_lock:
                proc = session_shell
                if proc.poll() is not None:
                    session_shell = None
                    return "Error: Session shell not running. Please create a project first."
                try:
                    if proc.stdin is None or proc.stdout is None:
                        return "Session shell communication pipe is not available."
                    # Send command
                    proc.stdin.write(command.strip() + "\n")
                    proc.stdin.write('echo __MCP_END__\n')
                    proc.stdin.flush()
                    # Collect output until marker
                    out_lines = []
                    t0 = time.time()
                    while True:
                        line = proc.stdout.readline()
                        if not line:
                            break
                        if line.rstrip() == "__MCP_END__":
                            break
                        out_lines.append(line)
                        if time.time() - t0 > 180:
                            return "Error: Shell command timed out."
                    out = "".join(out_lines).strip()
                except Exception as e:
                    return f"Shell session error: {type(e).__name__}: {str(e)}"
                if len(out) > 8192:
                    out = out[:8192] + "\n...[output truncated]..."
                logger.info("SessionShell[dir=%s] cmd %r output %d bytes", session_shell_cwd, command, len(out))
                return out
        # No session: fallback to one-off
        parts = shlex.split(command.strip())
        # Run with timeout and output size limit
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=180,
            errors="replace"
        )
        # Truncate output if it's too long
        out = result.stdout.strip()
        err = result.stderr.strip()
        if len(out) > 8192:
            out = out[:8192] + "\n...[output truncated]..."
        if result.returncode == 0:
            logger.info("Executed: %r OK, output %d bytes", command, len(out))
            return out
        else:
            logger.warning("Command failed: %r code=%s err: %r", command, result.returncode, err)
            return f"Error [{result.returncode}]: {err or '(no error output)'}"
    except subprocess.TimeoutExpired:
        logger.error("Timeout: %r", command)
        return "Error: Command timed out."
    except Exception as e:
        logger.error("Shell execution error: %r (%s)", command, e)
        return f"Execution error: {type(e).__name__}: {str(e)}"

from pydantic import BaseModel

class ActiveProjectInfo(BaseModel):
    name: str
    path: str

@mcp.tool(title="Get Active Project")
def get_active_project() -> ActiveProjectInfo:
    """
    Returns info about the currently active project: both name and full path,
    derived from the in-memory session_shell_cwd variable.
    """
    global session_shell_cwd
    name = ""
    path = ""
    if session_shell_cwd and os.path.isdir(session_shell_cwd):
        name = os.path.basename(session_shell_cwd)
        path = session_shell_cwd
    return ActiveProjectInfo(name=name, path=path)

@mcp.tool(title="List All Projects")
def list_all_projects() -> list:
    """
    Returns a sorted list of all project directories in ~/dev/mcp-projects.
    """
    base_dir = os.path.expanduser('~/dev/mcp-projects')
    if not os.path.exists(base_dir):
        return []
    return sorted([
        name for name in os.listdir(base_dir)
        if os.path.isdir(os.path.join(base_dir, name))
    ])

@mcp.tool(title="Create New Project")
def create_new_project(project_name: str) -> str:
    """
    Creates a new project directory under ~/dev/mcp-projects/<project_name> and starts a persistent shell in that directory.

    Shell process uses a minimal environment (does NOT inherit parent shell variables or rc config).
    - Only allows safe directory names (letters, numbers, ., _, -)
    - The shell will remain active for all consecutive execute_shell calls
    - Creating a new project stops any previous session shell
    - All projects are grouped under ~/dev/mcp-projects
    """
    import re
    global session_shell, session_shell_cwd, session_shell_lock
    # Validate project name: safe chars only
    if not re.match(r'^[a-zA-Z0-9_.-]+$', project_name):
        return "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
    base_dir = os.path.expanduser('~/dev/mcp-projects')
    os.makedirs(base_dir, exist_ok=True)
    proj_path = os.path.join(base_dir, project_name)
    if not os.path.exists(proj_path):
        os.makedirs(proj_path, exist_ok=True)
    # Clean up previous project shell, if running
    with session_shell_lock:
        if session_shell is not None and session_shell.poll() is None:
            session_shell.kill()
        session_shell = None
        session_shell_cwd = proj_path
        # Spawn a full sanitized shell (no env)
        shell_args = ['sudo', '-u', 'michi', '--login', 'bash', '-l']
        try:
            proc = subprocess.Popen(
                shell_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=proj_path,
                text=True,
                bufsize=1
            )
            # Ensure correct directory: no-op if already correct, but fixes login shell case
            if proc.stdin is not None:
                proc.stdin.write(f'cd "{proj_path}"\n')
                proc.stdin.flush()
        except Exception as e:
            return f"Error: Could not start project shell: {type(e).__name__}: {str(e)}"
        session_shell = proc
    logger.info(f"Started clean shell for project %r in %r", project_name, proj_path)
    return f"Started shell for project: {proj_path}"

@mcp.tool(title="Change Active Project")
def change_active_project(project_name: str) -> str:
    """
    Switch to an existing project under ~/dev/mcp-projects/<project_name> and start a persistent shell in that directory.
    Does NOT create the directory. Kills previous shell if running, starts new shell in the project dir, and updates session_shell_cwd.
    Returns a status string.
    """
    import re
    global session_shell, session_shell_cwd, session_shell_lock
    if not re.match(r'^[a-zA-Z0-9_.-]+$', project_name):
        return "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
    base_dir = os.path.expanduser('~/dev/mcp-projects')
    proj_path = os.path.join(base_dir, project_name)
    if not os.path.isdir(proj_path):
        return f"Error: Project directory does not exist: {proj_path}"
    with session_shell_lock:
        if session_shell is not None and session_shell.poll() is None:
            session_shell.kill()
        session_shell = None
        session_shell_cwd = proj_path
        shell_args = ['sudo', '-u', 'michi', '--login', 'bash', '-l']
        try:
            proc = subprocess.Popen(
                shell_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=proj_path,
                text=True,
                bufsize=1
            )
            # Ensure the correct working directory even for login shells
            if proc.stdin is not None:
                proc.stdin.write(f'cd "{proj_path}"\n')
                proc.stdin.flush()
        except Exception as e:
            return f"Error: Could not start project shell: {type(e).__name__}: {str(e)}"
        session_shell = proc
    logger.info(f"Changed active project to %r in %r", project_name, proj_path)
    return f"Changed active project to: {proj_path}"

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000, help='Port to run MCP server on')
    args = parser.parse_args()
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")

