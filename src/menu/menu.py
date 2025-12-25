import re
from prompt_toolkit.shortcuts import message_dialog
from . import menu_core
from .menu_state import MenuState
from .menu_app import MenuApp

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def handle_log_action(log_path: str, action: str, title: str) -> None:
    """Handles either viewing or clearing a log, showing appropriate dialog."""
    if action == 'view':
        content = menu_core.log_content(log_path)
        if content:
            content = ANSI_ESCAPE.sub('', content[-1000:])
        else:
            content = "[Log is empty or does not exist]"
        message_dialog(title=title, text=content).run()
    elif action == 'clear':
        menu_core.clear_log(log_path)
        message_dialog(
            title="Log Cleared",
            text=f"{title} has been cleared."
        ).run()


if __name__ == '__main__':
    state = None
    try:
        state = MenuState()
        app = MenuApp(state)
        app.run()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        if state:
            state.stop_mcp()
            state.stop_proxy()
