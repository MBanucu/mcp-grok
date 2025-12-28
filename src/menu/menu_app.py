import os
import re
from typing import Optional
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.application import Application
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import Button, Dialog, Label, TextArea
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.buffer import Buffer
from . import menu_core
from mcp_grok.config import config
from .menu_state import MenuState

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
            content = ANSI_ESCAPE.sub('', content)
        else:
            content = "[Log is empty or does not exist]"
        import asyncio
        asyncio.run(show_log_scrollable_dialog(content, title, log_path=log_path))


import asyncio

async def show_log_scrollable_dialog(content: str, title: str, log_path=None):
    # Set up TextArea for scrolling the content
    from prompt_toolkit.styles import Style
    style = Style.from_dict({'dialog': 'bg:#1d2230', 'dialog.body': 'bg:#181b29', 'dialog shadow': 'bg:#000000'})

    log_textarea = TextArea(
        text=content,
        scrollbar=True,
        line_numbers=False,
        read_only=True,
        focus_on_click=True,
        width=None,  # fill
        height=25,
    )
    # Move cursor to end for bottom scroll
    log_textarea.buffer.cursor_position = len(log_textarea.text)

    kb = KeyBindings()
    @kb.add('escape')
    @kb.add('q')
    def close_(event):
        event.app.exit()
    dialog = Dialog(
        title=title + ' (Scroll: ↑↓ PgUp/PgDn, q/Esc to close)',
        body=HSplit([
            log_textarea,
            Label(text="Press ↑, ↓, PgUp, PgDn to scroll; q or Esc to close.", style="class:dialog.body", dont_extend_height=True)
        ], padding=1),
        buttons=[],
        with_background=True
    )

    # Background log watcher
    async def poll_log():
        import os
        import time
        prev_content = log_textarea.text
        prev_stat = os.stat(log_path) if log_path and os.path.exists(log_path) else None
        while True:
            await asyncio.sleep(0.5)
            try:
                stat = os.stat(log_path) if log_path and os.path.exists(log_path) else None
                if not stat:
                    continue
                if prev_stat and stat.st_mtime == prev_stat.st_mtime and stat.st_size == prev_stat.st_size:
                    continue
                if log_path:
                    with open(log_path, 'r') as f:
                        new_content = f.read()
                else:
                    continue
                new_content = ANSI_ESCAPE.sub('', new_content)
                if new_content != prev_content:
                    user_was_at_end = (log_textarea.buffer.cursor_position == len(prev_content))
                    log_textarea.text = new_content
                    prev_content = new_content
                    prev_stat = stat
                    if user_was_at_end:
                        log_textarea.buffer.cursor_position = len(new_content)
            except Exception:
                pass
    
    app = Application(
        layout=Layout(dialog),
        key_bindings=kb,
        style=style,
        mouse_support=True,
        full_screen=True
    )
    # Launch the file watcher if a log_path is given
    if log_path:
        app.create_background_task(poll_log())
    await app.run_async()



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
            ('logs_mcp', 'View MCP Shell Logs'),
            ('clear_logs_mcp', 'Clear MCP Shell Log'),
            ('logs_proxy', 'View SuperAssistant Proxy Logs'),
            ('clear_logs_proxy', 'Clear Proxy Log'),
            ('logs_audit', 'View Audit Log'),
            ('clear_logs_audit', 'Clear Audit Log'),
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
            btn_container = HSplit(buttons, padding=0)
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
        if value in ('server', 'shutdown_mcp'):
            return self._handle_server_action(value)
        elif value in ('proxy', 'shutdown_proxy'):
            return self._handle_proxy_action(value)
        elif value in ('logs_mcp', 'clear_logs_mcp', 'logs_proxy', 'clear_logs_proxy'):
            return self._handle_log_action(value)
        elif value in ('vscode', 'shell', 'exit', None):
            return self._handle_external_action(value)
        return True

    def _handle_external_action(self, value: Optional[str]) -> bool:
        if value == 'vscode':
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

    def _handle_server_action(self, value: Optional[str]) -> bool:
        if value == 'server':
            self.state.start_mcp()
        elif value == 'shutdown_mcp':
            self.state.stop_mcp()
        return True

    def _handle_proxy_action(self, value: Optional[str]) -> bool:
        if value == 'proxy':
            self.state.start_proxy()
        elif value == 'shutdown_proxy':
            self.state.stop_proxy()
        return True

    def _handle_log_action(self, value: Optional[str]) -> bool:
        if value == 'logs_mcp':
            show_log(config.mcp_shell_log, "MCP Shell Logs")
        elif value == 'clear_logs_mcp':
            show_log(config.mcp_shell_log, "MCP Shell Log", clear=True)
        elif value == 'logs_proxy':
            show_log(config.proxy_log, "SuperAssistant Proxy Logs")
        elif value == 'clear_logs_proxy':
            show_log(config.proxy_log, "Proxy Log", clear=True)
        elif value == 'logs_audit':
            show_log(config.server_audit_log, "Audit Log")
        elif value == 'clear_logs_audit':
            show_log(config.server_audit_log, "Audit Log", clear=True)
        return True
