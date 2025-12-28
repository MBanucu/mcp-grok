import re
import sys
import argparse
import os
from .menu_state import MenuState
from .menu_app import MenuApp
from . import menu_core
from mcp_grok.config import config

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def main():
    parser = argparse.ArgumentParser(
        prog="mcp-grok-menu",
        description=(
            "Interactive terminal (TUI) menu for MCP "
            "project management."
        )
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--start-server', action='store_true',
        help='Start the MCP Server'
    )
    group.add_argument(
        '--stop-server', action='store_true',
        help='Shut down the MCP Server'
    )
    group.add_argument(
        '--start-proxy', action='store_true',
        help='Start the SuperAssistant Proxy'
    )
    group.add_argument(
        '--stop-proxy', action='store_true',
        help='Shut down the SuperAssistant Proxy'
    )
    group.add_argument(
        '--show-mcp-logs', action='store_true',
        help='Show MCP Server logs (tail)'
    )
    group.add_argument(
        '--clear-mcp-logs', action='store_true',
        help='Clear the MCP Server log'
    )
    group.add_argument(
        '--show-proxy-logs', action='store_true',
        help='Show SuperAssistant Proxy logs (tail)'
    )
    group.add_argument(
        '--clear-proxy-logs', action='store_true',
        help='Clear the SuperAssistant Proxy log'
    )
    group.add_argument(
        '--vscode', action='store_true',
        help='Launch VSCode in the current directory'
    )
    # Not adding shell as a CLI command (best in TTY only)

    args = parser.parse_args()

    # Action flags
    action_taken = False
    state = MenuState()
# (whitespace intentionally kept for PEP8 block indentation)

    if args.start_server:
        state.start_mcp()
        print("MCP Server started.")
        action_taken = True
    elif args.stop_server:
        state.stop_mcp()
        print("MCP Server stopped.")
        action_taken = True
    elif args.start_proxy:
        state.start_proxy()
        print("SuperAssistant Proxy started.")
        action_taken = True
    elif args.stop_proxy:
        state.stop_proxy()
        print("SuperAssistant Proxy stopped.")
        action_taken = True
    elif args.show_mcp_logs:
        content = menu_core.log_content(config.mcp_server_log)
        if content:
            print(ANSI_ESCAPE.sub('', content[-1000:]))
        else:
            print("[Log is empty or does not exist]")
        action_taken = True

    elif args.clear_mcp_logs:
        menu_core.clear_log(config.mcp_server_log)
        print("MCP Server log cleared.")
        action_taken = True
    elif args.show_proxy_logs:
        content = menu_core.log_content(config.proxy_log)
        if content:
            print(ANSI_ESCAPE.sub('', content[-1000:]))
        else:
            print("[Log is empty or does not exist]")
        action_taken = True

    elif args.clear_proxy_logs:
        menu_core.clear_log(config.proxy_log)
        print("SuperAssistant Proxy log cleared.")
        action_taken = True
    elif args.vscode:
        print("Launching VSCode...")
        os.system("code .")
        action_taken = True

    # If any CLI action taken, exit
    if action_taken:
        sys.exit(0)

    # If not TTY, print help as fallback
    if not sys.stdin.isatty():
        print(
            "\nNo interactive terminal detected "
            "and no command-line option given."
        )
        parser.print_usage()
        print(
            "\nFor documentation or non-interactive usage, "
            "see the README or run with --help."
        )
        sys.exit(1)

    # TTY + no args: run TUI
    try:
        state = MenuState()

        app = MenuApp(state)
        app.run()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        if state:
            state.stop_mcp()
            state.stop_proxy()


if __name__ == '__main__':
    main()
