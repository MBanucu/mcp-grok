import os
import functools
import logging
from typing import Optional
from pydantic import BaseModel
from mcp.types import ToolAnnotations
from .file_tools import (
    read_file as file_tools_read_file,
    write_file as file_tools_write_file,
)


class MCPGrokServer:
    def __init__(self, config):
        from .shell_manager import ShellManager
        from mcp.server.fastmcp import FastMCP
        self.config = config
        self.shell_manager = ShellManager(config)
        # project_manager is set after importing to avoid circular import
        from .project_manager import ProjectManager
        self.project_manager = ProjectManager(config, self.shell_manager)
        self.mcp = FastMCP(
            "ConsoleAccessServer",
            instructions=(
                "Console tool. Run shell commands in persistent project shells."
            ),
            stateless_http=True,
            json_response=True,
        )
        self._register_tools()

    def _log_tool_call(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logging.getLogger(__name__).info(
                "Tool called: %s args=%s kwargs=%s",
                func.__name__, args, kwargs,
            )
            return func(*args, **kwargs)

        return wrapper

    def _register_tools(self):
        mcp = self.mcp
        self._register_execute_tool(mcp)
        self._register_project_tools(mcp)
        self._register_file_tools(mcp)

    def _register_execute_tool(self, mcp):
        shell_manager = self.shell_manager

        @mcp.tool(
            title="Execute Any Shell Command",
            annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=False),
        )
        @self._log_tool_call
        def execute_shell(command: str = "") -> str:
            if not command.strip():
                return "Error: Command cannot be empty."
            return shell_manager.execute(command)

    def _register_project_tools(self, mcp):
        project_manager = self.project_manager
        shell_manager = self.shell_manager

        class ActiveProjectInfo(BaseModel):
            name: str
            path: str

        @mcp.tool(title="Get Active Project")
        @self._log_tool_call
        def get_active_project() -> ActiveProjectInfo:
            cwd = shell_manager.cwd
            name = os.path.basename(cwd) if cwd and os.path.isdir(cwd) else ""
            path = cwd if cwd and os.path.isdir(cwd) else ""
            return ActiveProjectInfo(name=name, path=path)

        @mcp.tool(title="List All Projects")
        @self._log_tool_call
        def list_all_projects() -> list:
            return project_manager.list_all()

        @mcp.tool(title="Create New Project")
        @self._log_tool_call
        def create_new_project(project_name: str) -> str:
            return project_manager.create_new(project_name)

        @mcp.tool(title="Change Active Project")
        @self._log_tool_call
        def change_active_project(project_name: str) -> str:
            return project_manager.change_active(project_name)

        # Expose tool methods for startup
        self.create_new_project = create_new_project
        self.change_active_project = change_active_project
        self.project_manager = project_manager

    def _register_file_tools(self, mcp):
        shell_manager = self.shell_manager

        @mcp.tool(
            title="Read File Anywhere",
            annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True),
        )
        @self._log_tool_call
        def read_file(
            file_path: str, limit: int = 2000, offset: int = 0
        ) -> str:
            if not os.path.isabs(file_path):
                cwd = shell_manager.cwd
                if not cwd:
                    return (
                        "Error: No active shell/project for relative path read."
                    )
                abs_path = os.path.join(cwd, file_path)
            else:
                abs_path = file_path
            return file_tools_read_file(abs_path, limit, offset)

        @mcp.tool(
            title="Write File Anywhere",
            annotations=ToolAnnotations(readOnlyHint=False, openWorldHint=True),
        )
        @self._log_tool_call
        def write_file(
            file_path: str,
            content: str,
            overwrite: bool = True,
            replace_lines_start: Optional[int] = None,
            replace_lines_end: Optional[int] = None,
            insert_at_line: Optional[int] = None,
            replaceAll: bool = False,
        ) -> str:
            if not os.path.isabs(file_path):
                cwd = shell_manager.cwd
                if not cwd:
                    return (
                        "Error: No active shell/project for relative path write."
                    )
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

    def startup(self):
        self.project_manager.ensure_projects_dir()
        default_proj_path = self.project_manager.project_path(
            self.config.default_project
        )
        if not os.path.exists(default_proj_path):
            logging.getLogger(__name__).info(
                (
                    f"Server startup: default project "
                    f"'{self.config.default_project}' does not exist. Creating new project."
                )
            )
            result = self.create_new_project(self.config.default_project)
            logging.getLogger(__name__).info(
                f"Default project creation result: {result}"
            )
        else:
            logging.getLogger(__name__).info(
                (
                    f"Server startup: default project "
                    f"'{self.config.default_project}' exists. Activating."
                )
            )
            result = self.change_active_project(self.config.default_project)
            logging.getLogger(__name__).info(
                f"Default project activation result: {result}"
            )

    def run(self):
        self.mcp.settings.port = self.config.port
        self.mcp.run(transport="streamable-http")
