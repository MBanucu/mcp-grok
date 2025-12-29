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

# Start the MCP-Grok server using flakes (recommended)
$ nix develop .#
# an interactive project management menu will pop up
# start the MCP Server and the SuperAssistant Proxy

# Start the MCP-Grok server manually
$ nix develop .#menuSuppressed --command python -m mcp_grok.mcp_grok_server

# Or with options using mcp-grok-server:
$ nix develop .#menuSuppressed --command python -m mcp_grok.mcp_grok_server --port 8099 --projects-dir ~/dev/my-projects --default-project testproject

# Start the SuperAssistant Proxy manually
$ nix develop .#menuSuppressed --command superassistant-proxy
```

> **Advanced:**
> For environments where you want to suppress the interactive menu (such as CI, scripts, or automation), use the `menuSuppressed` Nix flake shell:
>
> ```sh
> nix develop .#menuSuppressed
> ```
> For direct command-line usage, always wrap your shell command in `sh -c '...'`:
>
> ```sh
> nix develop .#menuSuppressed --command sh -c 'python -m pytest tests'
> ```
> This guarantees the shell is set up exactly as for development, with no interactive menu and full access to all CLI tools.



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

## Code Quality: Linting and Type Checking

This project uses both a linter and a static type checker, just like in CI. You can run these locally as follows (using the recommended Nix environment):

### Linting with flake8

[flake8](https://flake8.pycqa.org/) checks your code for common style, bug, and complexity issues.

```sh
nix develop .#menuSuppressed --command sh -c 'flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics && flake8 src tests --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics'
```

- The first run enforces strict errors; the second provides statistics with relaxed rules (like line length and complexity), matching CI.

### Type checking with pyright

[pyright](https://github.com/microsoft/pyright) performs static type checking for Python.

```sh
nix develop .#menuSuppressed --command pyright .
```

- This checks for type errors across the project, as in CI.

## Running Tests

```sh
nix develop .#menuSuppressed --command python -m pytest tests
```

Tests launch the server in a subprocess, simulate real tool API requests, and clean up after themselves. All main features are covered, including project management, shell execution, API error handling, and session management.

## Project Structure
- `src/mcp_grok/mcp_grok_server.py` : Main server entry; all logic.
- `tests/` : Pytest-based functional and integration tests.
- `pyproject.toml` : Dependency and build config.

## Security Notes
**Warning: NEVER expose this server to the public internet, as it allows shell access, though strictly sandboxed per project/user.**

## NixOS System Integration & Advanced Usage

### Use as a system package in NixOS

If you want to provide the `mcp-grok-server` as a system package on NixOS using the flake, add this flake as an input to your NixOS configuration:

```nix
# In your flakes-enabled NixOS configuration (flake.nix):
{
  inputs.mcp-grok.url = "github:MBanucu/mcp-grok";

  outputs = { self, nixpkgs, mcp-grok, ... }@inputs: {
    nixosConfigurations.mymachine = nixpkgs.lib.nixosSystem {
      # ...
      environment.systemPackages = [ mcp-grok.packages.${inputs.nixpkgs.system}.default ];
      # ...
    };
  };
}
```

> If not using flakes, see Overlay/Legacy Usage below for compatibility.

### Use as an input in another flake project

You can add this project as an input to your own flake-based Python/Nix project:

```nix
# In your flake.nix
{
  inputs.mcp-grok.url = "github:MBanucu/mcp-grok";

  outputs = { self, nixpkgs, mcp-grok, ... }@inputs: {
    # ...
    packages.${self.system}.mcp-grok = mcp-grok.packages.${self.system}.default;
    devShells.${self.system}.with-mcp-grok = nixpkgs.legacyPackages.${self.system}.mkShell {
      buildInputs = [ mcp-grok.packages.${self.system}.default ];
    };
  };
}
```

### Overlay / Legacy usage

If not using flakes, you can still use this project's `default.nix` as an overlay.
Example for configuration.nix:
```nix
{ config, pkgs, ... }:

{
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];

  nixpkgs.overlays = [
    (
      self: super:
      {
        mcp-grok = import (builtins.fetchGit {
          url = "https://github.com/MBanucu/mcp-grok.git";
        });
      }
    )
  ];

  environment.systemPackages = with pkgs; [
    mcp-grok
  ];
}
```

Add to NIX_PATH overlays or use in your legacy Nix expressions.

> The provided `default.nix` forwards transparently to the flake package for maximal compatibility as an overlay or with legacy `nix-build`.

---
Happy grokking, and feel free to contribute or file issues!

