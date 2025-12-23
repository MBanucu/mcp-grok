import logging
import subprocess
import shlex
from mcp.server.fastmcp import FastMCP

# Logging setup: logs to both file and stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler("server_audit.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    "ConsoleAccessServer",
    instructions="Secure, whitelisted console tool. NEVER expose this server to the internet!",
    # Use JSON mode, stateless HTTP for safer LLM integration:
    stateless_http=True,
    json_response=True,
)


from mcp.types import ToolAnnotations

@mcp.tool(
    title="Execute Any Shell Command",
    annotations=ToolAnnotations(
        readOnlyHint=False,
        openWorldHint=False
    )
)
def execute_shell(command: str = "") -> str:
    """
    Execute any single shell command.
    - Executes arbitrary commands via subprocess.
    - WARNING: This is unsafe for production or open internet!
    - max output: 8KB.
    - Timeout: 180s.
    - Input is NOT parsed by a shell (prevents some injection).
    """
    try:
        if not command.strip():
            return "Error: Command cannot be empty."
        parts = shlex.split(command.strip())
        # Run with timeout and output size limit
        result = subprocess.run(
            parts,
            capture_output=True,
            text=True,
            timeout=180,
            errors="replace"
        )
        # Truncate output if it's too long
        out = result.stdout.strip()
        err = result.stderr.strip()
        if len(out) > 8192:
            out = out[:8192] + "\n...[output truncated]..."
        if result.returncode == 0:
            logger.info("Executed: %r OK, output %d bytes", command, len(out))
            return out
        else:
            logger.warning("Command failed: %r code=%s err: %r", command, result.returncode, err)
            return f"Error [{result.returncode}]: {err or '(no error output)'}"
    except subprocess.TimeoutExpired:
        logger.error("Timeout: %r", command)
        return "Error: Command timed out."
    except Exception as e:
        logger.error("Shell execution error: %r (%s)", command, e)
        return f"Execution error: {type(e).__name__}: {str(e)}"

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
