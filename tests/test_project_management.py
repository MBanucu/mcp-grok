import os
import requests
from test_utils import mcp_create_project, mcp_execute_shell


def test_get_active_project(mcp_server):
    project_name = "proj_active_test"
    mcp_create_project(mcp_server, project_name)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": 18,
        "method": "tools/call",
        "params": {"name": "get_active_project"},
    }
    resp = requests.post(mcp_server, json=payload, headers=headers)
    assert resp.status_code == 200, f"get_active_project failed: {resp.text}"
    result = resp.json()["result"]
    struct = result.get("structuredContent")
    name = struct.get("name") if struct else result.get("name")
    path = struct.get("path") if struct else result.get("path")
    assert name == project_name, f"Active project mismatch: expected {project_name}, got {name!r}"
    assert path and path.endswith(project_name), f"Path mismatch: {path!r}"


def test_change_active_project(mcp_server):
    project_a = "projA"
    project_b = "projB"
    mcp_create_project(mcp_server, project_a)
    mcp_create_project(mcp_server, project_b)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    change_payload = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {"name": "change_active_project", "arguments": {"project_name": project_a}},
    }
    resp = requests.post(mcp_server, json=change_payload, headers=headers)
    assert resp.status_code == 200, f"Change active project failed: {resp.text}"
    try:
        result = resp.json()["result"]["structuredContent"]["result"]
        assert result.startswith("Started shell for project: "), (
            f"Response did not start with expected text. resp.text={resp.text}"
        )
        assert project_a in result, f"Expected '{project_a}' in result. resp.text={resp.text}"
    except KeyError as e:
        raise AssertionError(f"KeyError {e} when accessing response JSON. Full response: {resp.text}") from e
    get_payload = {
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {"name": "get_active_project"},
    }
    get_resp = requests.post(mcp_server, json=get_payload, headers=headers)
    assert get_resp.status_code == 200
    result = get_resp.json()["result"]
    struct = result.get("structuredContent")
    name = struct.get("name") if struct else None
    assert name == project_a, f"Active project mismatch: expected {project_a}, got {name!r}"
    DEV_ROOT = os.path.expanduser("~/dev/mcp-projects-test")
    echo_output = mcp_execute_shell(mcp_server, "echo $PWD")
    assert echo_output.endswith(f"{DEV_ROOT}/{project_a}"), f"Shell $PWD: got {echo_output!r}"
    names = ["projA", "projB", "projC"]
    for n in names:
        mcp_create_project(mcp_server, n)
        assert os.path.isdir(os.path.join(DEV_ROOT, n)), f"Project dir not created for {n}"
    list_payload = {
        "jsonrpc": "2.0",
        "id": 17,
        "method": "tools/call",
        "params": {"name": "list_all_projects"},
    }
    resp = requests.post(mcp_server, json=list_payload, headers=headers)
    assert resp.status_code == 200, f"List projects failed: {resp.text}"
    result = resp.json()["result"]
    if isinstance(result, dict) and "content" in result:
        project_names = [item.get("text") for item in result["content"] if isinstance(item, dict)]
    else:
        project_names = result
    assert set(names).issubset(set(project_names)), f"Projects missing: {names} not in {project_names}"
