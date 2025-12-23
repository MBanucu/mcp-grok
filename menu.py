import os
import re
from prompt_toolkit.shortcuts import radiolist_dialog, message_dialog
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
            result = radiolist_dialog(
                title='MCP Project Dev Menu',
                text='Select an action:',
                values=menu_items,
            ).run()
            if result == 'server':
                if not (mcp_proc and mcp_proc.poll() is None):
                    mcp_proc = menu_core.start_server()
            elif result == 'shutdown_mcp':
                menu_core.stop_server(mcp_proc)
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
                menu_core.stop_server(mcp_proc)
                menu_core.stop_proxy(proxy_proc)
                shell = os.environ.get("SHELL", "/bin/sh")
                os.execvp(shell, [shell])
            elif result == 'exit' or result is None:
                print("Exiting...")
                menu_core.stop_server(mcp_proc)
                menu_core.stop_proxy(proxy_proc)
                break
    except KeyboardInterrupt:
        print("\nInterrupted.")
        menu_core.stop_server(mcp_proc)
        menu_core.stop_proxy(proxy_proc)

if __name__ == '__main__':
    main()
