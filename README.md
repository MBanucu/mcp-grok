# mcp-grok

A secure, project-oriented persistent shell management server, built on FastMCP. Enables robust, auditable remote shell execution and project environment management via a fast, stateless JSON-RPC API.

## Features
- **Persistent, sandboxed project shells**: Each project gets its own login shell subprocess, running as a specific user (default: `michi`).
- **Stateless, JSON-based API**: All operations (create project, switch, run shell command, list projects, query active project) are exposed via FastMCP tools.
- **Thread-safe, robust shell management**: Only one session shell per project, with strong locking and pipe safety.
- **Automatic logging**: All session events and output are logged to `server_audit.log` and stdout.
- **Configurable via CLI**: Set port, projects directory, and default project name on startup.
- **Tested and production-ready**: With extensive and realistic end-to-end tests.

## Requirements
- Python 3.12+
- [Nix](https://nixos.org/) (for reproducible dev environments via `nix-shell`)
- Or: install Python dependencies in `pyproject.toml` (`mcp[cli]`, `prompt-toolkit`, `pytest`, etc)

## Quickstart

```sh
# Clone the repository
$ git clone https://github.com/MBanucu/mcp-grok.git
$ cd mcp-grok

# Start the server using nix-shell (recommended)
$ nix-shell --run 'python src/server.py'

# Or with options:
$ nix-shell --run 'python src/server.py --port 8099 --projects-dir ~/dev/my-projects --default-project testproject'
```

The server runs locally by default, listens on the configured port, and exposes a FastMCP-compatible HTTP+JSON endpoint at `/mcp` (usually, e.g. http://localhost:8000/mcp).

## Usage/API

You communicate with the server via JSON-RPC POST requests. Example tools and their purposes:

- **execute_shell(command: str):** Execute a shell command in the currently active persistent shell.
- **create_new_project(project_name: str):** Create new persistent project directory and start a clean shell.
- **change_active_project(project_name: str):** Switch to another project (if exists) and run its shell.
- **list_all_projects():** List all available project directories.
- **get_active_project():** Return structured info on the current active project (name, absolute path).

### Example: Run a Command
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "execute_shell",
    "arguments": {"command": "whoami"}
  }
}
```

### Example: Create New Project
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "create_new_project",
    "arguments": {"project_name": "myproject"}
  }
}
```

See `tests/test_mcp.py` for more programmatic usage patterns and expected outputs.

## Running Tests

```sh
nix-shell --run 'uv run pytest tests'
```

Tests launch the server in a subprocess, simulate real tool API requests, and clean up after themselves. All main features are covered, including project management, shell execution, API error handling, and session management.

## Project Structure
- `src/server.py` : Main server entry; all logic.
- `tests/` : Pytest-based functional and integration tests.
- `pyproject.toml` : Dependency and build config.

## Security Notes
**Warning: NEVER expose this server to the public internet, as it allows shell access, though strictly sandboxed per project/user.**

## License

This project is licensed under the GNU General Public License v3.0. See [LICENSE](LICENSE) for details.

---
Happy grokking, and feel free to contribute or file issues!
