import os
import re
import subprocess
from typing import Optional

from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import Button, Dialog, Label
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.key_binding import KeyBindings

import menu_core

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


class MenuState:
    """
    Holds current process state for MCP server and proxy process.
    """

    def __init__(self):
        self.mcp_proc: Optional[subprocess.Popen] = None
        self.proxy_proc: Optional[subprocess.Popen] = None

    def is_mcp_running(self) -> bool:
        return self.mcp_proc is not None and self.mcp_proc.poll() is None

    def is_proxy_running(self) -> bool:
        return self.proxy_proc is not None and self.proxy_proc.poll() is None

    def start_mcp(self):
        if not self.is_mcp_running():
            self.mcp_proc = menu_core.server_manager.start_server()

    def stop_mcp(self):
        menu_core.server_manager.stop_server()
        self.mcp_proc = None

    def start_proxy(self):
        if not self.is_proxy_running():
            self.proxy_proc = menu_core.start_proxy()

    def stop_proxy(self):
        menu_core.stop_proxy(self.proxy_proc)
        self.proxy_proc = None


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


def show_log(
    log_path: str, title: str, clear: bool = False
) -> None:
    """
    Show or clear a log file using a dialog.

    Args:
        log_path (str): The path to the log file.
        title (str): Dialog title.
        clear (bool): If True, clear the log rather than view it.
    """
    if clear:
        menu_core.clear_log(log_path)
        message_dialog(
            title="Log Cleared",
            text=f"{title} has been cleared."
        ).run()
    else:
        content = menu_core.log_content(log_path)
        if content:
            content = ANSI_ESCAPE.sub('', content[-1000:])
        else:
            content = "[Log is empty or does not exist]"
        message_dialog(title=title, text=content).run()


class MenuApp:
    """
    Main application for interactive TUI menu for MCP project.
    Handles menu rendering, input, and command dispatch.
    """

    def __init__(self, state: MenuState):
        self.state = state
        self.active_index = 0

    def get_menu_items(self) -> list[tuple[str, str]]:
        """
        Get the menu items for the current menu state.

        Returns:
            list[tuple[str, str]]: (value, label) pairs for menu rendering.
        """
        items = []
        if self.state.is_mcp_running():
            items.append(('shutdown_mcp', 'Shut down MCP Server'))
        else:
            items.append(('server', 'Run MCP Server'))
        if self.state.is_proxy_running():
            items.append(('shutdown_proxy', 'Shut down SuperAssistant Proxy'))
        else:
            items.append(('proxy', 'Run SuperAssistant Proxy'))
        items += [
            ('logs_mcp', 'View MCP Server Logs'),
            ('clear_logs_mcp', 'Clear MCP Server Log'),
            ('logs_proxy', 'View SuperAssistant Proxy Logs'),
            ('clear_logs_proxy', 'Clear Proxy Log'),
            ('vscode', 'Run VSCode'),
            ('shell', 'Open Interactive Shell'),
            ('exit', 'Exit'),
        ]
        return items

    def build_buttons(
        self, menu_items: list[tuple[str, str]], selected: dict
    ) -> list[Button]:
        """
        Build buttons for the given menu items. Each button sets selection and
        exits the app on press.

        Args:
            menu_items (list of tuple): List of (value, label) pairs.
            selected (dict): Dict to hold the selected value for menu result.

        Returns:
            list[Button]: List of prompt_toolkit Button widgets.
        """
        buttons = []
        from prompt_toolkit.application import get_app
        for index, (value, label) in enumerate(menu_items):
            def make_handler(v):

                def handler():
                    selected['value'] = v
                    get_app().exit()
                return handler
            btn = Button(text=label, handler=make_handler(value))
            btn.window.align = WindowAlign.LEFT
            buttons.append(btn)
        return buttons

    def run(self) -> None:
        """
        Launch the menu loop. Redraws/rebuilds menu after each user action.
        """
        while True:
            menu_items = self.get_menu_items()
            selected = {'value': None}
            buttons = self.build_buttons(menu_items, selected)
            btn_container = HSplit(buttons, padding=1)
            dialog = Dialog(
                title='MCP Project Dev Menu',
                body=HSplit([
                    Label(
                        text=(
                            "Use Arrow/Tab/Shift-Tab/Up/Down to select, "
                            "Enter to activate, Mouse click if supported."
                        ),
                    ),
                    btn_container,
                ], padding=1),
                with_background=True
            )
            kb = KeyBindings()

            @kb.add('down')
            def move_down(event):
                layout = event.app.layout
                btns = btn_container.children
                try:
                    i = btns.index(layout.current_window)
                except ValueError:
                    i = 0
                next_i = (i + 1) % len(btns)
                layout.focus(btns[next_i])
                self.active_index = next_i

            @kb.add('up')
            def move_up(event):
                layout = event.app.layout
                btns = btn_container.children
                try:
                    i = btns.index(layout.current_window)
                except ValueError:
                    i = 0
                prev_i = (i - 1 + len(btns)) % len(btns)
                layout.focus(btns[prev_i])
                self.active_index = prev_i
            global app
            app = Application(
                layout=Layout(
                    dialog, focused_element=buttons[self.active_index].window
                ),
                key_bindings=kb,
                full_screen=True,
                mouse_support=True,
            )
            app.run()
            result = selected['value']
            if not self.handle_selection(result):
                break

    def handle_selection(self, value: Optional[str]) -> bool:
        """
        Handle a menu action.
        Returns False to exit the menu loop, True to continue.
        """
        if value == 'server':
            self.state.start_mcp()
        elif value == 'shutdown_mcp':
            self.state.stop_mcp()
        elif value == 'proxy':
            self.state.start_proxy()
        elif value == 'shutdown_proxy':
            self.state.stop_proxy()
        elif value == 'logs_mcp':
            show_log(menu_core.MCP_LOGFILE, "MCP Server Logs (tail)")
        elif value == 'clear_logs_mcp':
            show_log(menu_core.MCP_LOGFILE, "MCP Server Log", clear=True)
        elif value == 'logs_proxy':
            show_log(
                menu_core.PROXY_LOGFILE,
                "SuperAssistant Proxy Logs (tail)"
            )
        elif value == 'clear_logs_proxy':
            show_log(menu_core.PROXY_LOGFILE, "Proxy Log", clear=True)
        elif value == 'vscode':
            print("Launching VSCode...")
            os.system("code .")
        elif value == 'shell':
            print("Starting interactive shell. Type 'exit' to leave.")
            self.state.stop_mcp()
            self.state.stop_proxy()
            shell = os.environ.get("SHELL", "/bin/sh")
            os.execvp(shell, [shell])
        elif value == 'exit' or value is None:
            print("Exiting...")
            self.state.stop_mcp()
            self.state.stop_proxy()
            return False
        return True


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
