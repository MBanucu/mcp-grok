# Copilot Instructions for mcp-grok

## Project Overview

mcp-grok is a secure, project-oriented persistent shell management server built on FastMCP. It enables robust, auditable remote shell execution and project environment management via a fast, stateless JSON-RPC API.

**Key Features:**
- Persistent, sandboxed project shells (each project gets its own login shell subprocess)
- Stateless, JSON-based API via FastMCP
- Thread-safe, robust shell management
- Automatic logging to `server_audit.log`
- Python 3.12+ with Nix-based development environment

## Development Environment

This project uses **Nix** for reproducible development environments. Always use the Nix shell for development, linting, and testing to ensure parity with CI workflows.

### Setup

```bash
# Enter development environment with interactive menu
nix develop .#

# Enter development environment without menu (for CI/scripts)
nix develop .#menuSuppressed
```

For direct command execution:
```bash
nix develop .#menuSuppressed --command sh -c 'your-command-here'
```

## Build, Lint, and Test Commands

### Testing
Run the full test suite:
```bash
nix develop .#menuSuppressed --command python -m pytest tests
```

Tests are comprehensive and cover:
- Project management
- Shell execution
- API error handling
- Session management
- File operations (read/write/delete)

### Linting
Code must pass strict flake8 checks:
```bash
# Strict errors (CI will fail on these)
nix develop .#menuSuppressed --command sh -c 'flake8 src tests --count --select=E9,F63,F7,F82 --show-source --statistics'

# Full linting with statistics
nix develop .#menuSuppressed --command sh -c 'flake8 src tests --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics'
```

**Line length:** Target 79 characters (strict). The second flake8 run shows statistics for lines up to 127 characters but doesn't enforce them.

### Type Checking
Static typing is checked via Pyright:
```bash
nix develop .#menuSuppressed --command pyright .
```

All public APIs and method arguments should be fully typed.

## Code Quality Standards

1. **PEP 8 Compliance:** Follow Python PEP 8 style guidelines
2. **Type Annotations:** All public APIs must have complete type annotations
3. **Line Length:** Target 79 characters (strict limit enforced by CI)
4. **Complexity:** Keep cyclomatic complexity ≤ 10
5. **Documentation:** Maintain docstrings for public classes, functions, and modules
6. **Testing:** All features must have corresponding tests

## Project Structure

```
src/
  mcp_grok/          # Main MCP server implementation
    mcp_grok_server.py  # Main server entry point
    server.py           # Server core
    project_manager.py  # Project management
    shell_manager.py    # Shell subprocess management
    file_tools.py       # File operation tools
    config.py           # Configuration
    server_daemon.py    # Daemon mode
    server_client.py    # Client utilities
  menu/              # Interactive menu system
tests/               # Pytest-based tests
  fixtures/          # Test fixtures and utilities
  test_*.py          # Test modules
```

## Architecture and Design Patterns

1. **FastMCP-based:** Uses FastMCP framework for JSON-RPC API
2. **Thread-safe:** Strong locking and pipe safety for concurrent operations
3. **Stateless API:** All operations exposed as discrete tools
4. **Sandboxed Execution:** Each project runs in its own shell subprocess
5. **Audit Logging:** All operations logged for traceability

## API Tools

The server exposes these tools via JSON-RPC:
- `execute_shell(command: str)` - Execute command in active shell
- `create_new_project(project_name: str)` - Create new project
- `change_active_project(project_name: str)` - Switch projects
- `list_all_projects()` - List all projects
- `get_active_project()` - Get current project info
- `read_file(file_path: str, limit: int = 2000, offset: int = 0)` - Read up to `limit` lines from file, starting at line `offset` (0-based)
- `write_file(file_path: str, content: str, overwrite: bool = True, replace_lines_start: Optional[int] = None, replace_lines_end: Optional[int] = None, insert_at_line: Optional[int] = None, replaceAll: bool = False)` - Write/update file with various modes:
  - Basic write: Set `content` and `overwrite`
  - Line replacement: Use `replace_lines_start` (inclusive, 0-based) and `replace_lines_end` (exclusive, 0-based)
  - Line insertion: Use `insert_at_line` (0-based, inserts before this line)
  - Full replacement: Set `replaceAll=True`
  - Delete lines: Use `replace_lines_start`/`end` with empty `content`

## Security Considerations

**CRITICAL:** Never expose this server to the public internet. It allows shell access, though sandboxed per project/user.

Key security principles:
- Server runs locally by default
- Each project isolated in its own shell subprocess
- Default user: `michi` (configurable)
- All operations logged for audit trail
- No public internet exposure allowed

## Dependencies

Core dependencies (see `pyproject.toml`):
- `mcp[cli]` - FastMCP framework
- `prompt-toolkit` - Interactive menu
- `pytest` - Testing (optional dependency)
- `requests` - HTTP client for tests (optional)
- `pyright` - Type checking (optional)
- `flake8` - Linting (optional)

## Workflow and Branching

1. **Never commit directly to `main`** - Always use feature branches
2. **Conventional Commits:** Use prefixes like `feat:`, `fix:`, `refactor:`, `docs:`, `test:`
3. **Pull Requests:** Required for all changes; include clear descriptions
4. **Testing:** All tests must pass before merging
5. **Linting:** Code must pass strict linter checks
6. **Type Checking:** No type errors allowed

## Making Changes

When modifying code:
1. Create a feature branch with descriptive name
2. Run tests before making changes to understand baseline
3. Make minimal, focused changes
4. Add/update tests for new functionality
5. Run linters and type checker
6. Update documentation (README.md) if needed
7. Ensure no zombie processes or orphaned resources
8. Submit PR with clear description and motivation

## Common Tasks

### Starting the server
```bash
# Via menu
nix develop .#

# Manually
nix develop .#menuSuppressed --command python -m mcp_grok.mcp_grok_server

# With options
nix develop .#menuSuppressed --command python -m mcp_grok.mcp_grok_server --port 8099 --projects-dir ~/dev/my-projects --default-project testproject
```

### Running specific tests
```bash
nix develop .#menuSuppressed --command python -m pytest tests/test_mcp.py
nix develop .#menuSuppressed --command python -m pytest tests/test_shell_features.py -v
```

### Debugging
- Check `server_audit.log` for audit trail
- Use `-v` flag with pytest for verbose test output
- Tests are self-cleaning and should not leave orphaned processes

## File Naming and Organization

- Test files: `test_*.py` in `tests/` directory
- Source files: Descriptive names in `src/mcp_grok/` or `src/menu/`
- Fixtures: Organized in `tests/fixtures/`
- Use snake_case for Python files and functions
- Use PascalCase for class names

## Additional Notes

- Tests launch the server in a subprocess and clean up automatically
- The server listens on configured port (default: 8000)
- API endpoint typically at `/mcp` (e.g., `http://localhost:8000/mcp`)
- All session events logged to stdout and `server_audit.log`
- Update both this file and README.md when making significant changes

## Related Files

- `README.md` - User-facing documentation and quickstart
- `.github/instructions/memory.instruction.md` - AI agent workflow instructions
- `pyproject.toml` - Python project configuration
- `.github/workflows/python-package.yml` - CI/CD configuration
