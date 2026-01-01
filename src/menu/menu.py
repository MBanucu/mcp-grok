import re
import sys
import argparse
import os
from .menu_state import MenuState
from .menu_app import MenuApp
from . import menu_core
from mcp_grok.config import config

ANSI_ESCAPE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def handle_start_server(state: MenuState) -> bool:
    state.start_mcp()
    print("MCP Server started.")
    return True


def handle_stop_server(state: MenuState) -> bool:
    state.stop_mcp()
    print("MCP Server stopped.")
    return True


def handle_start_proxy(state: MenuState) -> bool:
    state.start_proxy()
    print("SuperAssistant Proxy started.")
    return True


def handle_stop_proxy(state: MenuState) -> bool:
    state.stop_proxy()
    print("SuperAssistant Proxy stopped.")
    return True


def handle_show_mcp_logs() -> bool:
    content = menu_core.log_content(os.path.expanduser(f'~/.mcp-grok/{config.log_timestamp}_{config.port}_mcp-shell.log'))
    if content:
        print(ANSI_ESCAPE.sub('', content[-1000:]))
    else:
        print("[Log is empty or does not exist]")
    return True


def handle_clear_mcp_logs() -> bool:
    menu_core.clear_log(os.path.expanduser(f'~/.mcp-grok/{config.log_timestamp}_{config.port}_mcp-shell.log'))
    print("MCP Shell log cleared.")
    return True


def handle_show_proxy_logs() -> bool:
    content = menu_core.log_content(config.proxy_log)
    if content:
        print(ANSI_ESCAPE.sub('', content[-1000:]))
    else:
        print("[Log is empty or does not exist]")
    return True


def handle_clear_proxy_logs() -> bool:
    menu_core.clear_log(config.proxy_log)
    print("SuperAssistant Proxy log cleared.")
    return True


def handle_vscode() -> bool:
    print("Launching VSCode...")
    os.system("code .")
    return True


def handle_cli_action(args: argparse.Namespace, state: MenuState) -> bool:
    if args.start_server:
        return handle_start_server(state)
    if args.stop_server:
        return handle_stop_server(state)
    if args.start_proxy:
        return handle_start_proxy(state)
    if args.stop_proxy:
        return handle_stop_proxy(state)
    if args.show_mcp_logs:
        return handle_show_mcp_logs()
    if args.clear_mcp_logs:
        return handle_clear_mcp_logs()
    if args.show_proxy_logs:
        return handle_show_proxy_logs()
    if args.clear_proxy_logs:
        return handle_clear_proxy_logs()
    if args.vscode:
        return handle_vscode()
    return False


def main() -> None:
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
        help='Show MCP Shell logs (tail)'
    )
    group.add_argument(
        '--clear-mcp-logs', action='store_true',
        help='Clear the MCP Shell log'
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
    state = MenuState()

    if handle_cli_action(args, state):
        sys.exit(0)

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
            state.stop_daemon()


if __name__ == '__main__':
    main()
