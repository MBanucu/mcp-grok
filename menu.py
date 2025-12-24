import os
import re
from prompt_toolkit.shortcuts import message_dialog
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, HSplit
from prompt_toolkit.widgets import Button, Dialog
from prompt_toolkit.layout.containers import WindowAlign
from prompt_toolkit.layout.containers import WindowAlign

import menu_core

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")

def handle_log_action(log_path, action, title):
    if action == 'view':
        content = menu_core.log_content(log_path)
        if content:
            content = ANSI_ESCAPE.sub('', content[-1000:])
        else:
            content = "[Log is empty or does not exist]"
        message_dialog(title=title, text=content).run()
    elif action == 'clear':
        menu_core.clear_log(log_path)
        message_dialog(title="Log Cleared", text=f"{title} has been cleared.").run()

def view_logs(log_path, title):
    handle_log_action(log_path, 'view', title)

def clear_logs(log_path, title):
    handle_log_action(log_path, 'clear', title)

def main():
    mcp_proc = None
    proxy_proc = None
    active_index = 0
    try:
        while True:
            menu_items = []
            if mcp_proc and mcp_proc.poll() is None:
                menu_items.append(('shutdown_mcp', 'Shut down MCP Server'))
            else:
                menu_items.append(('server', 'Run MCP Server'))
            if proxy_proc and proxy_proc.poll() is None:
                menu_items.append(('shutdown_proxy', 'Shut down SuperAssistant Proxy'))
            else:
                menu_items.append(('proxy', 'Run SuperAssistant Proxy'))
            menu_items += [
                ('logs_mcp', 'View MCP Server Logs'),
                ('clear_logs_mcp', 'Clear MCP Server Log'),
                ('logs_proxy', 'View SuperAssistant Proxy Logs'),
                ('clear_logs_proxy', 'Clear Proxy Log'),
                ('vscode', 'Run VSCode'),
                ('shell', 'Open Interactive Shell'),
                ('exit', 'Exit'),
            ]
            # Build vertical buttons using prompt_toolkit Application
            selected = {'value': None}
            buttons = [
                Button(
                    text=label,
                    handler=(lambda idx=index, v=value: (selected.update({'value': v}), active_index := idx, app.exit(), None)[-1])
                )
                for index, (value, label) in enumerate(menu_items)
            ]
            for btn in buttons:
                btn.window.align = WindowAlign.LEFT

            from prompt_toolkit.widgets import Label
            from prompt_toolkit.key_binding import KeyBindings

            btn_container = HSplit(buttons, padding=1)
            dialog = Dialog(
                title='MCP Project Dev Menu',
                body=HSplit([
                    Label(text="Use Arrow/Tab/Shift-Tab/Up/Down to select, Enter to activate, Mouse click if supported."),
                    btn_container,
                ], padding=1),
                with_background=True
            )
            kb = KeyBindings()
            from prompt_toolkit.layout import Window

            @kb.add('down')
            def move_focus_down(event):
                layout = event.app.layout
                btns = btn_container.children
                current_window = layout.current_window
                btn_windows = btns  # Each is a Button (focusable)
                try:
                    i = btn_windows.index(current_window)
                except ValueError:
                    i = 0
                next_i = (i + 1) % len(btn_windows)
                layout.focus(btn_windows[next_i])
                nonlocal active_index
                active_index = next_i

            @kb.add('up')
            def move_focus_up(event):
                layout = event.app.layout
                btns = btn_container.children
                current_window = layout.current_window
                btn_windows = btns  # Each is a Button (focusable)
                try:
                    i = btn_windows.index(current_window)
                except ValueError:
                    i = 0
                prev_i = (i - 1 + len(btn_windows)) % len(btn_windows)
                layout.focus(btn_windows[prev_i])
                nonlocal active_index
                active_index = prev_i

            app = Application(layout=Layout(dialog, focused_element=buttons[active_index].window), key_bindings=kb, full_screen=True, mouse_support=True)
            app.run()
            result = selected['value']
            if result == 'server':
                if not (mcp_proc and mcp_proc.poll() is None):
                    mcp_proc = menu_core.server_manager.start_server()
            elif result == 'shutdown_mcp':
                menu_core.server_manager.stop_server()
                mcp_proc = None
            elif result == 'proxy':
                if not (proxy_proc and proxy_proc.poll() is None):
                    proxy_proc = menu_core.start_proxy()
            elif result == 'shutdown_proxy':
                menu_core.stop_proxy(proxy_proc)
                proxy_proc = None
            elif result == 'logs_mcp':
                view_logs(menu_core.MCP_LOGFILE, "MCP Server Logs (tail)")
            elif result == 'clear_logs_mcp':
                clear_logs(menu_core.MCP_LOGFILE, "MCP Server Log")
            elif result == 'logs_proxy':
                view_logs(menu_core.PROXY_LOGFILE, "SuperAssistant Proxy Logs (tail)")
            elif result == 'clear_logs_proxy':
                clear_logs(menu_core.PROXY_LOGFILE, "Proxy Log")
            elif result == 'vscode':
                print("Launching VSCode...")
                os.system("code .")
            elif result == 'shell':
                print("Starting interactive shell. Type 'exit' to leave.")
                menu_core.server_manager.stop_server()
                menu_core.stop_proxy(proxy_proc)
                shell = os.environ.get("SHELL", "/bin/sh")
                os.execvp(shell, [shell])
            elif result == 'exit' or result is None:
                print("Exiting...")
                menu_core.server_manager.stop_server()
                menu_core.stop_proxy(proxy_proc)
                break

    except KeyboardInterrupt:
        print("\nInterrupted.")
        menu_core.server_manager.stop_server()
        menu_core.stop_proxy(proxy_proc)


if __name__ == '__main__':
    main()
