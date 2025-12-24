import logging
from src.config import Config
from src.shell_manager import ShellManager
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel
from mcp.types import ToolAnnotations


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
