"""Router behaviour against fake stdio MCP backends."""
import io
import json
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from multiplc.config import ConfigError, load_config  # noqa: E402
from multiplc.router import LIST_TOOL, Router, StdioServer  # noqa: E402

FAKE = textwrap.dedent('''
    import json, sys
    tools = [{"name": n, "description": n, "inputSchema": {"type": "object"}} for n in sys.argv[1].split(",")]
    for line in sys.stdin:
        m = json.loads(line)
        if "id" not in m:
            continue
        if m["method"] == "initialize":
            r = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake", "version": "1"}}
        elif m["method"] == "tools/list":
            r = {"tools": tools}
        elif m["method"] == "tools/call":
            if m["params"]["name"] == "boom":
                sys.exit(3)
            if m["params"]["name"] == "rpcfail":
                print(json.dumps({"jsonrpc": "2.0", "id": m["id"], "error": {"code": -32602, "message": "bad args"}}), flush=True)
                continue
            r = {"content": [{"type": "text", "text": json.dumps({"called": m["params"]["name"], "args": m["params"].get("arguments")})}]}
        else:
            r = {}
        print(json.dumps({"jsonrpc": "2.0", "id": m["id"], "result": r}), flush=True)
''')


@pytest.fixture
def config(tmp_path):
    fake = tmp_path / "fake.py"
    fake.write_text(FAKE)

    def make(backends):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({"backends": backends}))
        return path

    def backend(vendor, tools, **extra):
        return {"vendor": vendor, "command": sys.executable, "args": [str(fake), ",".join(tools)], **extra}

    return make, backend


def _router(specs):
    router = Router(specs)
    router.start({"name": "test", "version": "0"})
    return router


def _payload(result):
    return json.loads(result["content"][0]["text"])


def test_tools_are_prefixed_and_routed_to_their_backend(config):
    make, backend = config
    router = _router(load_config(make({
        "gx": backend("mitsubishi", ["create_project", "list_projects"]),
        "tia": backend("siemens", ["Connect", "CompileSoftware"]),
    })))
    try:
        names = {tool["name"] for tool in router.list_tools()["tools"]}
        assert {"mitsubishi_create_project", "siemens_CompileSoftware", LIST_TOOL} <= names
        result = router.call_tool({"name": "siemens_CompileSoftware", "arguments": {"softwarePath": "PLC_1"}})
        assert _payload(result) == {"called": "CompileSoftware", "args": {"softwarePath": "PLC_1"}}
    finally:
        router.stop()


def test_live_plc_tools_are_hidden_and_blocked_through_call_tool(config):
    make, backend = config
    router = _router(load_config(make({"tia": backend("siemens", ["DownloadToPlc", "GoOnline", "CallTool", "Connect"])})))
    try:
        names = {tool["name"] for tool in router.list_tools()["tools"]}
        assert "siemens_DownloadToPlc" not in names and "siemens_GoOnline" not in names
        assert router.call_tool({"name": "siemens_DownloadToPlc", "arguments": {}})["isError"]
        blocked = router.call_tool({"name": "siemens_CallTool", "arguments": {"name": "DownloadToPlc"}})
        assert blocked["isError"] and "not exposed" in _payload(blocked)["error"]
        allowed = router.call_tool({"name": "siemens_CallTool", "arguments": {"name": "SetPlcTag"}})
        assert _payload(allowed)["called"] == "CallTool"
    finally:
        router.stop()


def test_allow_reenables_a_default_denied_tool(config):
    make, backend = config
    router = _router(load_config(make({"cx": backend("omron", ["delete_rung"], allow=["delete_rung"])})))
    try:
        assert "omron_delete_rung" in {tool["name"] for tool in router.list_tools()["tools"]}
    finally:
        router.stop()


def test_failed_backend_is_reported_and_others_keep_working(config):
    make, backend = config
    specs = load_config(make({
        "broken": {"vendor": "omron", "command": str(Path(sys.executable).with_name("does-not-exist"))},
        "gx": backend("mitsubishi", ["list_projects", "boom"]),
    }))
    router = _router(specs)
    try:
        status = {row["name"]: row for row in router.backend_status()["backends"]}
        assert status["broken"]["status"] == "error" and status["gx"]["status"] == "running"
        assert _payload(router.call_tool({"name": "mitsubishi_list_projects", "arguments": {}}))["called"] == "list_projects"
        crashed = router.call_tool({"name": "mitsubishi_boom", "arguments": {}})
        assert crashed["isError"] and "exited" in _payload(crashed)["error"]
    finally:
        router.stop()


def test_duplicate_prefix_and_unknown_vendor_are_rejected(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"backends": {"a": {"vendor": "omron", "command": "x"}, "b": {"vendor": "omron", "command": "y"}}}))
    with pytest.raises(ConfigError, match="prefix"):
        load_config(path)
    path.write_text(json.dumps({"backends": {"a": {"vendor": "rockwell", "command": "x"}}}))
    with pytest.raises(ConfigError, match="vendor"):
        load_config(path)


def test_disabled_backend_is_skipped(tmp_path):
    path = tmp_path / "c.json"
    path.write_text(json.dumps({"backends": {"gx3": {"enabled": False, "vendor": "mitsubishi", "command": "unsupported"},
                                             "cx": {"vendor": "omron", "command": "x"}}}))
    assert [spec.name for spec in load_config(path)] == ["cx"]


def test_stdio_server_passes_backend_rpc_errors_through(config):
    make, backend = config
    router = Router(load_config(make({"cx": backend("omron", ["rpcfail", "project_summary"])})))
    requests = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "omron_rpcfail", "arguments": {}}},
        {"jsonrpc": "2.0", "id": 3, "method": "nope"},
    ]
    stdin = io.StringIO("".join(json.dumps(r) + "\n" for r in requests))
    stdout = io.StringIO()
    StdioServer(router, stdin, stdout).serve()
    replies = {m["id"]: m for m in map(json.loads, stdout.getvalue().splitlines())}
    assert replies[1]["result"]["serverInfo"]["name"] == "multi-plc-agent"
    assert replies[2]["error"] == {"code": -32602, "message": "bad args"}
    assert replies[3]["error"]["code"] == -32601
