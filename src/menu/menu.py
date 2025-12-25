import re
from prompt_toolkit.shortcuts import message_dialog
from . import menu_core
from .menu_state import MenuState
from .menu_app import MenuApp

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


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
