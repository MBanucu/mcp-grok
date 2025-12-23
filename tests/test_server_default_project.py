import tempfile
import subprocess
import time
import os
import shutil
import requests

def test_default_project_activation():
    """
    Test that starting the server with --default-project activates/creates that project.
    """
    projects_dir = tempfile.mkdtemp(prefix="mcp-grok-defaultproj-")
    port = 8128
    default_project = "autotest_default_proj"
    server_proc = subprocess.Popen([
        "python", "server.py",
        "--port", str(port),
        "--projects-dir", projects_dir,
        "--default-project", default_project],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    try:
        # Wait for startup indication or timeout
        t0 = time.time()
        ready = False
        while time.time() - t0 < 30:
            # Defensive: If pipe closed, poll for exit
            if server_proc.stdout is not None:
                ln = server_proc.stdout.readline()
                if not ln:
                    if server_proc.poll() is not None:
                        raise RuntimeError("Server exited early: code %r" % server_proc.returncode)
                    continue
                if "Uvicorn running on http://" in ln or "Uvicorn running on http://127.0.0.1" in ln:
                    ready = True
                    break
            else:
                # If no stdout, sleep+poll
                if server_proc.poll() is not None:
                    raise RuntimeError("Server process exited prematurely (no stdout)")
                time.sleep(0.2)
        assert ready, "Timeout waiting for server startup"
        # Check project dir
        default_proj_path = os.path.join(projects_dir, default_project)
        assert os.path.isdir(default_proj_path), f"Default project directory was not created: {default_proj_path}"
        # Query active project via API
        url = f"http://localhost:{port}/mcp"
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        payload = {
            "jsonrpc": "2.0", "id": 32177, "method": "tools/call",
            "params": {"name": "get_active_project"}
        }
        for _ in range(20):
            try:
                r = requests.post(url, json=payload, headers=headers, timeout=4)
                if r.status_code == 200:
                    break
            except Exception:
                time.sleep(0.3)
        else:
            raise AssertionError("get_active_project did not succeed after retries")
        result = r.json()["result"]
        struct = result.get("structuredContent")
        if struct:
            name = struct.get("name")
            path = struct.get("path")
        else:
            name = result.get("name")
            path = result.get("path")
        assert name == default_project, f"Expected active project '{default_project}', got '{name}'"
        assert path and os.path.abspath(path) == os.path.abspath(default_proj_path), f"Active project path mismatch: got '{path}', expected '{default_proj_path}'"
    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()
        shutil.rmtree(projects_dir, ignore_errors=True)
