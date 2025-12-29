import logging
import functools
from contextlib import asynccontextmanager
from .config import config
from .file_tools import read_file as file_tools_read_file, write_file as file_tools_write_file
import os
from pydantic import BaseModel
from typing import Optional
from mcp.types import ToolAnnotations

def _suppress_closed_resource_error(record):
    msg = record.getMessage()
    if "ClosedResourceError" in msg:
        return False
    exc = getattr(record, "exc_info", None)
    if exc and exc[0] and "ClosedResourceError" in str(exc[0]):
        return False
    return True

def setup_logging():
    logfile = config.server_audit_log
    logdir = os.path.dirname(logfile)
    try:
        os.makedirs(logdir, exist_ok=True)
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
    for name, log in logging.root.manager.loggerDict.items():
        if isinstance(log, logging.Logger):
            log.addFilter(_suppress_closed_resource_error)
    logging.getLogger().addFilter(_suppress_closed_resource_error)

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
        logging.getLogger(__name__).info(f"Tool called: {func.__name__} args={args} kwargs={kwargs}")
        return func(*args, **kwargs)
    return wrapper

# --- ENTRY POINT ---
def main():
    import argparse
    from .shell_manager import ShellManager
    from mcp.server.fastmcp import FastMCP

    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=config.port, help='Port to run MCP server on')
    parser.add_argument('--projects-dir', type=str, default=config.projects_dir, help='Base directory for MCP projects')
    parser.add_argument('--default-project', type=str, default=config.default_project, help='Default project to activate on server start')
    args = parser.parse_args()
    config.port = args.port
    config.projects_dir = args.projects_dir
    config.default_project = args.default_project

    setup_logging()
    shell_manager = ShellManager(config)
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
        if not command.strip():
            return "Error: Command cannot be empty."
        return shell_manager.execute(command)

    @mcp.tool(title="Get Active Project")
    @log_tool_call
    def get_active_project() -> ActiveProjectInfo:
        import os
        cwd = shell_manager.cwd
        name = os.path.basename(cwd) if cwd and os.path.isdir(cwd) else ""
        path = cwd if cwd and os.path.isdir(cwd) else ""
        return ActiveProjectInfo(name=name, path=path)

    @mcp.tool(title="List All Projects")
    @log_tool_call
    def list_all_projects() -> list:
        import os
        ensure_projects_dir()
        return sorted([
            name for name in os.listdir(config.projects_dir)
            if os.path.isdir(os.path.join(config.projects_dir, name))
        ])

    @mcp.tool(title="Create New Project")
    @log_tool_call
    def create_new_project(project_name: str) -> str:
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
            import traceback
            tb = traceback.format_exc()
            return (
                f"Error: failed to stop previous shell:\n"
                f"Type: {type(e).__name__}\n"
                f"Message: {e}\n"
                f"Traceback:\n{tb}"
            )
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
        import os
        if not os.path.isabs(file_path):
            cwd = shell_manager.cwd
            if not cwd:
                return "Error: No active shell/project for relative path read."
            abs_path = os.path.join(cwd, file_path)
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
        import os
        if not os.path.isabs(file_path):
            cwd = shell_manager.cwd
            if not cwd:
                return "Error: No active shell/project for relative path write."
            abs_path = os.path.join(cwd, file_path)
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

    # Server startup logic
    ensure_projects_dir()
    default_proj_path = project_path(config.default_project)
    if not os.path.exists(default_proj_path):
        logging.getLogger(__name__).info(
            f"Server startup: default project '{config.default_project}' "
            f"does not exist. Creating new project."
        )
        result = create_new_project(config.default_project)
        logging.getLogger(__name__).info(f"Default project creation result: {result}")
    else:
        logging.getLogger(__name__).info(
            f"Server startup: default project '{config.default_project}' "
            f"exists. Activating."
        )
        result = change_active_project(config.default_project)
        logging.getLogger(__name__).info(f"Default project activation result: {result}")
    mcp.settings.port = config.port
    mcp.run(transport="streamable-http")

if __name__ == "__main__":
    main()
