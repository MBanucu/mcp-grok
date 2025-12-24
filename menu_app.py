import os
import re
from typing import Optional
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import Button, Dialog, Label
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.key_binding import KeyBindings
import menu_core
from menu_state import MenuState

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def show_log(log_path: str, title: str, clear: bool = False) -> None:
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

    def build_buttons(self, menu_items: list[tuple[str, str]], selected: dict) -> list[Button]:
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
