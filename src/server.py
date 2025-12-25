import logging
from src.config import Config
from src.shell_manager import ShellManager
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from mcp.types import ToolAnnotations
import os
import pathlib
from typing import Optional

config = Config()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler(config.log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

shell_manager = ShellManager(config)

# --- PROJECT MANAGEMENT HELPERS ---
def safe_project_name(name: str) -> bool:
    import re
    return re.match(r'^[a-zA-Z0-9_.-]+$', name) is not None

def project_path(name: str) -> str:
    import os
    return os.path.join(config.projects_dir, name)

def ensure_projects_dir():
    import os
    os.makedirs(config.projects_dir, exist_ok=True)

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
    shell_manager.stop_shell()
    return shell_manager.start_shell(proj_path)

# --- NEW - READ FILE TOOL ---
@mcp.tool(
    title="Read File Anywhere",
    annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True)
)
def read_file(file_path: str, limit: int = 2000, offset: int = 0) -> str:
    """
    Read and return up to `limit` lines from `file_path`, starting at line `offset`,
    anywhere on the filesystem. Returns file content as text, or an error string if
    the file is not found, is too large, is a directory, or appears binary.
    - Files anywhere on the system can be accessed (subject to server process permissions).
    - `limit` (max lines): default 2000, hard capped at 5000. Offset must be >= 0.
    - Reading directories is blocked. Large/binary file detection is enforced.
    """
    try:
        abs_fp = pathlib.Path(file_path).expanduser().resolve()
        if not abs_fp.exists() or not abs_fp.is_file():
            return f"Error: File does not exist or is not a file: {abs_fp}"
        if abs_fp.stat().st_size > 10 * 1024 * 1024:
            return "Error: File too large (>10MB)."
        # Try to determine if binary
        try:
            with open(abs_fp, "rb") as f:
                sample = f.read(512)
                if b"\0" in sample:
                    return "Error: File appears to be binary."
        except Exception as e:
            return f"Error: Cannot check if file is binary: {type(e).__name__}: {e}"
        # Read text lines
        max_lines = min(5000, max(1, limit))
        start = max(0, offset)
        content_lines = []
        lines_read = 0
        truncated = False
        try:
            with open(abs_fp, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f):
                    if idx < start:
                        continue
                    if lines_read >= max_lines:
                        truncated = True
                        break
                    content_lines.append(line.rstrip("\n\r"))
                    lines_read += 1
        except Exception as e:
            return f"Error: Could not read file: {type(e).__name__}: {e}"
        out = "\n".join(content_lines)
        if truncated:
            out += "\n...[output truncated]..."
        return out.strip()
    except Exception as e:
        return f"Error: Unexpected error in read_file: {type(e).__name__}: {e}"

# --- WRITE FILE TOOL ---

@mcp.tool(
    title="Write File Anywhere",
    annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True)
)
def write_file(
    file_path: str,
    content: str,
    overwrite: bool = True,
    replace_lines_start: Optional[int] = None,
    replace_lines_end: Optional[int] = None,
    insert_at_line: Optional[int] = None
) -> str:
    """
    Write `content` to the specified `file_path`. Will overwrite by default.

    Line indices:
    - All line numbers/indices (`replace_lines_start`, `replace_lines_end`, `insert_at_line`) are 0-based (the first line is line 0).
    - For line replacement, `replace_lines_start` is inclusive and `replace_lines_end` is exclusive ([start:end]).
    - For insertion, `insert_at_line` is 0-based (insert before this line; insert at 0 is before the first line).
    - If `content` is an empty string (""), then the specified replace range will be deleted entirely (no replacement lines inserted).

    Protections:
    - Canonicalizes/resolves file_path. Refuses if writing outside the server's permissions.
    - Won't overwrite if `overwrite=False` and file exists.
    - Refuses to write >10MB at once. Enforces UTF-8 encoding.
    - Won't write to device nodes, symlinks, or system directories.
    - Reports all errors with clear reason.
    """
    try:
        abs_fp = pathlib.Path(file_path).expanduser().resolve()
        # Block device/special file, symlink, or directory
        if abs_fp.exists():
            if abs_fp.is_symlink():
                return f"Error: Target is a symlink: {abs_fp}"
            if abs_fp.is_dir():
                return f"Error: Refusing to write to a directory: {abs_fp}"
            if abs_fp.is_block_device() or abs_fp.is_char_device():
                return f"Error: Refusing to write to device file: {abs_fp}"
            if not overwrite:
                return f"Error: File already exists and overwrite=False: {abs_fp}"
        if len(content.encode("utf-8")) > 10 * 1024 * 1024:
            return "Error: Content too large (>10MB)."
        # Disallow writing to obvious system dirs/files as a hardening step
        system_prefixes = ["/bin", "/sbin", "/lib", "/etc", "/usr", "/var", "/dev", "/proc", "/sys", "/boot", "/root"]
        if any(str(abs_fp).startswith(prefix + "/") or str(abs_fp) == prefix for prefix in system_prefixes):
            return f"Error: Refusing to write to system directory: {abs_fp}"
        # Safe mode: bring parent dir into existence if not present (replicates mkdir -p for project usage)
        abs_fp.parent.mkdir(parents=True, exist_ok=True)
        # Smart content: MUTUALLY EXCLUSIVE: replace and insert
        if (replace_lines_start is not None and replace_lines_end is not None) and insert_at_line is not None:
            return "Error: Cannot specify both replace_lines and insert_at_line."
        # Smart content: line replacement
        if replace_lines_start is not None and replace_lines_end is not None:
            if not abs_fp.exists() or not abs_fp.is_file():
                return f"Error: File does not exist for line replacement: {abs_fp}"
            try:
                with open(abs_fp, "r", encoding="utf-8") as f:
                    old_lines = f.readlines()
                start = int(replace_lines_start)
                end = int(replace_lines_end)
                if start < 0 or end < 0 or end < start:
                    return "Error: Invalid line range requested."
                content_is_empty = content == ""
                lines_before = old_lines[:start] if start < len(old_lines) else old_lines
                lines_after = old_lines[end:] if end < len(old_lines) else []
                if start > len(old_lines):
                    lines_before = old_lines + ["\n"] * (start - len(old_lines))
                if content_is_empty:
                    new_lines = lines_before + lines_after  # Delete the slice
                else:
                    content_lines = content.splitlines(keepends=True)
                    new_lines = lines_before + content_lines + lines_after
                with open(abs_fp, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                action = "Deleted" if content_is_empty else f"replaced"
                return f"Success: Lines {start}:{end} {action} in {abs_fp}"
            except Exception as e:
                return f"Error: Failed to replace lines: {type(e).__name__}: {e}"
        # Smart content: insertion
        if insert_at_line is not None:
            try:
                if abs_fp.exists() and abs_fp.is_file():
                    with open(abs_fp, "r", encoding="utf-8") as f:
                        old_lines = f.readlines()
                else:
                    old_lines = []
                insert_at = max(0, int(insert_at_line or 0))
                content_lines = content.splitlines(keepends=True)
                if insert_at > len(old_lines):
                    lines_before = old_lines + ["\n"] * (insert_at - len(old_lines))
                else:
                    lines_before = old_lines[:insert_at]
                lines_after = old_lines[insert_at:] if insert_at <= len(old_lines) else []
                new_lines = lines_before + content_lines + lines_after
                with open(abs_fp, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                return f"Success: Inserted at line {insert_at} in {abs_fp}"
            except Exception as e:
                return f"Error: Failed to insert lines: {type(e).__name__}: {e}"
        # Write content (full or truncated)
        mode = "w" if overwrite else "x"
        try:
            with open(abs_fp, mode, encoding="utf-8") as f:
                f.write(content)
        except FileExistsError:
            return f"Error: File exists and overwrite=False: {abs_fp}"
        except Exception as e:
            return f"Error: Failed to write file: {type(e).__name__}: {e}"
        return f"Success: File written to {abs_fp}"
    except Exception as e:
        return f"Error: Unexpected error in write_file: {type(e).__name__}: {e}"

# --- ENTRY POINT ---
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--port', type=int, default=8000,
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
