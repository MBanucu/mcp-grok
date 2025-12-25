import requests


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
