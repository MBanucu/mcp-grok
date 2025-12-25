import os
import requests

# Existing API functions

def api_write_file(server_url, file_path, content, **extra_args):
    args = {"file_path": file_path, "content": content}
    args.update(extra_args)
    payload = {
        "jsonrpc": "2.0",
        "id": 8808,
        "method": "tools/call",
        "params": {
            "name": "write_file",
            "arguments": args,
        },
    }
    headers = {"Accept": "application/json"}
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"HTTP failure: {resp.text}"
    data = resp.json()
    assert "result" in data, f"No result: {data}"
    result = data["result"]
    if isinstance(result, dict):
        return result.get("structuredContent", {}).get("result") or result.get("content") or str(result)
    return str(result)

def api_read_file(server_url, file_path, limit=None, offset=None):
    args = {"file_path": file_path}
    if limit is not None:
        args["limit"] = limit
    if offset is not None:
        args["offset"] = offset
    payload = {
        "jsonrpc": "2.0",
        "id": 8809,
        "method": "tools/call",
        "params": {
            "name": "read_file",
            "arguments": args,
        },
    }
    headers = {"Accept": "application/json"}
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"HTTP failure: {resp.text}"
    data = resp.json()
    assert "result" in data, f"No result: {data}"
    result = data["result"]
    if isinstance(result, dict):
        if "structuredContent" in result and "result" in result["structuredContent"]:
            return result["structuredContent"]["result"]
        if "content" in result and isinstance(result["content"], list):
            return "\n".join(
                str(item.get("text", str(item))) for item in result["content"] if isinstance(item, dict)
            )
    return str(result)

# MCP helpers for splitting tests

def mcp_create_project(server_url, project_name):
    """Create project via MCP API."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "create_new_project",
            "arguments": {"project_name": project_name},
        },
    }
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"Failed: {resp.text}"
    data = resp.json()
    assert "result" in data, f"JSON-RPC error or missing result: {data}"
    test_dir = os.path.expanduser("~/dev/mcp-projects-test")
    assert os.path.isdir(os.path.join(test_dir, project_name)), f"Project dir not created: {test_dir}/{project_name}"
    return os.path.join(test_dir, project_name)

def mcp_execute_shell(server_url, command):
    """Run shell command via MCP API."""
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "execute_shell",
            "arguments": {"command": command},
        },
    }
    resp = requests.post(server_url, json=payload, headers=headers)
    assert resp.status_code == 200, f"Shell failed: {resp.text}"
    data = resp.json()
    return _extract_shell_output(data["result"])

def _extract_shell_output(result):
    content = result.get("content", result) if isinstance(result, dict) else result
    if isinstance(content, list):
        return "\n".join(
            item.get("text", str(item)) for item in content if isinstance(item, dict)
        ).strip()
    return str(content).strip()

def get_last_non_empty_line(output):
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""
