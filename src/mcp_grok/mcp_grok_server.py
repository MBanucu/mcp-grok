import logging
import functools
from .config import config
from .shell_manager import ShellManager
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from mcp.types import ToolAnnotations
from typing import Optional
from .file_tools import read_file as file_tools_read_file, write_file as file_tools_write_file


import os
# Ensure log directory exists and is writable, or fallback to /tmp
logfile = config.server_audit_log
logdir = os.path.dirname(logfile)
try:
    os.makedirs(logdir, exist_ok=True)
    # Try to open in append mode to check writability
    with open(logfile, "a"):
        pass
except Exception:
    logfile = "/tmp/server_audit.log"
    logdir = "/tmp"
    os.makedirs(logdir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(logfile),
        logging.StreamHandler()
    ]
)

# Suppress noisy anyio.ClosedResourceError from logs


def _suppress_closed_resource_error(record):
    msg = record.getMessage()
    if "ClosedResourceError" in msg:
        return False
    exc = getattr(record, "exc_info", None)
    if exc and exc[0] and "ClosedResourceError" in str(exc[0]):
        return False
    return True


# Apply log suppression filter to all loggers (root and children)
for name, log in logging.root.manager.loggerDict.items():
    if isinstance(log, logging.Logger):
        log.addFilter(_suppress_closed_resource_error)
logging.getLogger().addFilter(_suppress_closed_resource_error)

logger = logging.getLogger(__name__)

shell_manager = ShellManager(config)


# --- PROJECT MANAGEMENT HELPERS ---


def safe_project_name(name: str) -> bool:
    import re
    return re.match(r'^[a-zA-Z0-9_.-]+$', name) is not None


def project_path(name: str) -> str:
    return os.path.join(config.projects_dir, name)


def ensure_projects_dir():
    os.makedirs(config.projects_dir, exist_ok=True)


def log_tool_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        logger.info(f"Tool called: {func.__name__} args={args} kwargs={kwargs}")
        return func(*args, **kwargs)
    return wrapper


# --- MCP SERVER SETUP ---
mcp = FastMCP(
    "ConsoleAccessServer",
    instructions=(
        "Console tool. Run shell commands in "
        "persistent project shells."
    ),
    stateless_http=True,
    json_response=True,
)


class ActiveProjectInfo(BaseModel):
    name: str
    path: str


@mcp.tool(
    title="Execute Any Shell Command",
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=False)
)
@log_tool_call
def execute_shell(command: str = "") -> str:
    """
    Execute any single shell command in the persistent shell
    of the active project.
    - Executes arbitrary commands via session shell.
    - max output: 8KB.
    - Timeout: 180s.
    """
    if not command.strip():
        return "Error: Command cannot be empty."
    return shell_manager.execute(command)


@mcp.tool(title="Get Active Project")
@log_tool_call
def get_active_project() -> ActiveProjectInfo:
    """
    Returns info about the currently active project: both name and full path.
    """
    import os
    cwd = shell_manager.cwd
    name = os.path.basename(cwd) if cwd and os.path.isdir(cwd) else ""
    path = cwd if cwd and os.path.isdir(cwd) else ""
    return ActiveProjectInfo(name=name, path=path)


@mcp.tool(title="List All Projects")
@log_tool_call
def list_all_projects() -> list:
    """
    Returns a sorted list of all project directories in ~/dev/mcp-projects.
    """
    import os
    ensure_projects_dir()
    return sorted([
        name for name in os.listdir(config.projects_dir)
        if os.path.isdir(os.path.join(config.projects_dir, name))
    ])


@mcp.tool(title="Create New Project")
@log_tool_call
def create_new_project(project_name: str) -> str:
    """
    Creates a new project directory under
    ~/dev/mcp-projects/<project_name> and starts a persistent shell
    in that directory.
    """
    if not safe_project_name(project_name):
        return (
            "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
        )
    ensure_projects_dir()
    proj_path = project_path(project_name)
    import os
    if not os.path.exists(proj_path):
        os.makedirs(proj_path, exist_ok=True)
    shell_manager.stop_shell()
    return shell_manager.start_shell(proj_path)


@mcp.tool(title="Change Active Project")
@log_tool_call
def change_active_project(project_name: str) -> str:
    """
    Switch to an existing project under
    ~/dev/mcp-projects/<project_name> and start a persistent shell in that
    directory.
    Does NOT create the directory.
    Kills previous shell if running and starts new shell in the
    project dir.
    """
    if not safe_project_name(project_name):
        return (
            "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
        )
    proj_path = project_path(project_name)
    import os
    if not os.path.isdir(proj_path):
        return f"Error: Project directory does not exist: {proj_path}"
    try:
        shell_manager.stop_shell()
    except Exception as e:
        return f"Error: failed to stop previous shell: {e}"
    try:
        return shell_manager.start_shell(proj_path)
    except Exception as e:
        return f"Error: failed to start shell in '{proj_path}': {e}"


@mcp.tool(
    title="Read File Anywhere",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True)
)
@log_tool_call
def read_file(file_path: str, limit: int = 2000, offset: int = 0) -> str:
    """
    Read and return up to `limit` lines from the given `file_path`, starting at line `offset`.

    - Returns file content as text, or a clear error string
      if the file is not found, is too large, is a directory, or appears binary.
    - Files anywhere on the server’s filesystem can be accessed, subject to process file permissions.
    - `limit` (maximum lines): defaults to 2000, capped at 5000. Offset must be >= 0.
    - Reading directories is blocked. Large/binary file detection is enforced for safety.
    - If the file exceeds 10MB, or appears as binary (null bytes), a clear error message is returned instead.
      Partial reads are truncated with a notice.
    """
    import os
    # If file_path is relative, resolve relative to shell_manager.cwd
    if not os.path.isabs(file_path):
        if not shell_manager.cwd:
            return "Error: No active shell/project for relative path read."
        abs_path = os.path.join(shell_manager.cwd, file_path)
    else:
        abs_path = file_path
    return file_tools_read_file(abs_path, limit, offset)


@mcp.tool(
    title="Write File Anywhere",
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True)
)
@log_tool_call
def write_file(
    file_path: str,
    content: str,
    overwrite: bool = True,
    replace_lines_start: Optional[int] = None,
    replace_lines_end: Optional[int] = None,
    insert_at_line: Optional[int] = None,
    replaceAll: bool = False
) -> str:
    """
    Write `content` to the specified `file_path`. Will overwrite by default, and supports advanced line replacement/insertion.

    If replaceAll=True, the entire contents of the target file will be
    replaced with the given `content`, regardless of any line or range
    arguments. This is equivalent to a full overwrite from start to end of file.
    Default is False, preserving previous line/insert replacement behavior.

    Line index behavior:
    - All line numbers (`replace_lines_start`, `replace_lines_end`, `insert_at_line`) are 0-based (first line is 0).
    - To replace lines, `replace_lines_start` is inclusive, `replace_lines_end` is exclusive ([start:end]).
    - To insert lines, `insert_at_line=0` inserts before the first line; higher values insert before that line index.
    - If `content` is an empty string, the specified replace range is deleted.

    Protections and safeguards:
    - Canonicalizes/resolves the path; refuses to write outside server permissions.
    - Will not overwrite if `overwrite=False` and file exists.
    - Refuses to write more than 10MB at once, and always uses UTF-8 encoding.
    - Will not write to device nodes, symlinks, or system directories.
    - All failures and rejections are reported with clear error reasons for troubleshooting.
    """
    import os
    # If file_path is relative, resolve relative to shell_manager.cwd
    if not os.path.isabs(file_path):
        if not shell_manager.cwd:
            return "Error: No active shell/project for relative path write."
        abs_path = os.path.join(shell_manager.cwd, file_path)
    else:
        abs_path = file_path
    return file_tools_write_file(
        abs_path,
        content,
        overwrite,
        replace_lines_start,
        replace_lines_end,
        insert_at_line,
        replaceAll,
    )


# --- ENTRY POINT ---
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=config.port,
        help='Port to run MCP server on'
    )
    parser.add_argument(
        '--projects-dir', type=str, default=config.projects_dir,
        help='Base directory for MCP projects'
    )
    parser.add_argument(
        '--default-project', type=str, default=config.default_project,
        help='Name for the default project to activate on server start'
    )
    args = parser.parse_args()
    config.port = args.port
    config.projects_dir = args.projects_dir
    config.default_project = args.default_project
    ensure_projects_dir()
    default_proj_path = project_path(config.default_project)
    import os
    if not os.path.exists(default_proj_path):
        logger.info(
            f"Server startup: default project '{config.default_project}' "
            f"does not exist. Creating new project."
        )
        result = create_new_project(config.default_project)
        logger.info(f"Default project creation result: {result}")
    else:
        logger.info(
            f"Server startup: default project '{config.default_project}' "
            f"exists. Activating."
        )
        result = change_active_project(config.default_project)
        logger.info(f"Default project activation result: {result}")
    mcp.settings.port = config.port
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
