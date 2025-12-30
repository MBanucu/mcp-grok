import os
import re


class ProjectManager:
    def __init__(self, config, shell_manager):
        self.config = config
        self.shell_manager = shell_manager

    def safe_name(self, name: str) -> bool:
        return re.match(r'^[a-zA-Z0-9_.-]+$', name) is not None

    def project_path(self, name: str) -> str:
        return os.path.join(self.config.projects_dir, name)

    def ensure_projects_dir(self):
        os.makedirs(self.config.projects_dir, exist_ok=True)

    def list_all(self):
        self.ensure_projects_dir()
        return sorted([
            name for name in os.listdir(self.config.projects_dir)
            if os.path.isdir(os.path.join(self.config.projects_dir, name))
        ])

    def create_new(self, name: str) -> str:
        if not self.safe_name(name):
            return (
                "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
            )
        self.ensure_projects_dir()
        proj_path = self.project_path(name)
        if not os.path.exists(proj_path):
            os.makedirs(proj_path, exist_ok=True)
        self.shell_manager.stop_shell()
        return self.shell_manager.start_shell(proj_path)

    def change_active(self, name: str) -> str:
        if not self.safe_name(name):
            return (
                "Error: Unsafe project name. Only letters, numbers, _ . - allowed."
            )
        proj_path = self.project_path(name)
        if not os.path.isdir(proj_path):
            return f"Error: Project directory does not exist: {proj_path}"
        try:
            self.shell_manager.stop_shell()
        except Exception as e:
            import traceback

            tb = traceback.format_exc()
            return (
                f"Error: failed to stop previous shell:\n"
                f"Type: {type(e).__name__}\nMessage: {e}\nTraceback:\n{tb}"
            )
        try:
            return self.shell_manager.start_shell(proj_path)
        except Exception as e:
            return f"Error: failed to start shell in '{proj_path}': {e}"
