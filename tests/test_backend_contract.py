"""Contract every in-repo backend must keep, checked over real stdio like the router uses it.

A new backend under backends/<vendor>/<vendor>_mcp is picked up automatically.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BACKENDS = sorted(p.parent.parent.name for p in ROOT.glob("backends/*/*_mcp/server.py"))
# Tools that would touch a running controller. No in-repo backend may offer them.
ONLINE = re.compile(r"(download|upload|online|monitor|force|transfer|write_plc|run_plc|stop_plc)", re.I)
NAME = re.compile(r"^[a-z][a-z0-9_]{0,47}$")  # leaves room for a vendor prefix under the 64-char client limit
WRITE = re.compile(r"^(write|new)_")


def rpc(vendor: str, messages: list[dict], *args: str) -> list[dict]:
    proc = subprocess.run([sys.executable, "-m", f"{vendor}_mcp", *args],
                          input="".join(json.dumps(m) + "\n" for m in messages).encode(),
                          cwd=ROOT / "backends" / vendor, capture_output=True, timeout=60)
    assert proc.returncode == 0, proc.stderr.decode(errors="replace")[-2000:]
    return [json.loads(line) for line in proc.stdout.decode("utf-8").splitlines() if line.strip()]


def test_every_backend_is_discovered():
    assert {"codesys", "delta", "haiwell", "outseal", "schneider", "sysmac"} <= set(BACKENDS)


@pytest.mark.parametrize("vendor", BACKENDS)
def test_stdio_contract(vendor):
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}}
    replies = rpc(vendor, [init, {"jsonrpc": "2.0", "method": "notifications/initialized"},
                           {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                           {"jsonrpc": "2.0", "id": 3, "method": "no/such"},
                           {"jsonrpc": "2.0", "id": 4, "method": "ping"}])
    by_id = {r["id"]: r for r in replies}
    assert set(by_id) == {1, 2, 3, 4}, "notifications must not be answered"
    info = by_id[1]["result"]
    assert info["serverInfo"]["name"] == f"{vendor}-mcp" and info["capabilities"]["tools"] is not None
    assert by_id[3]["error"]["code"] == -32601
    tools = by_id[2]["result"]["tools"]
    names = [t["name"] for t in tools]
    assert len(names) == len(set(names)) and "validate" in names
    for t in tools:
        assert NAME.match(t["name"]), t["name"]
        assert not ONLINE.search(t["name"]), f"{t['name']} looks like a live-PLC tool"
        assert t["description"].strip()
        schema = t["inputSchema"]
        assert schema["type"] == "object" and isinstance(schema.get("properties", {}), dict)
        assert set(schema.get("required", [])) <= set(schema.get("properties", {}))


@pytest.mark.parametrize("vendor", BACKENDS)
def test_write_tools_refuse_without_allow_write(vendor, tmp_path):
    list_req = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]
    tools = rpc(vendor, list_req)[0]["result"]["tools"]
    writers = [t for t in tools if WRITE.match(t["name"])]
    assert writers, "a backend needs at least one write/new tool"
    calls = []
    for i, t in enumerate(writers, start=10):
        args = {"path": str(tmp_path / f"out{i}"), "rungs": [], "name": "x", "board": "x", "main": []}
        args = {k: v for k, v in args.items() if k in t["inputSchema"].get("properties", {})}
        calls.append({"jsonrpc": "2.0", "id": i, "method": "tools/call", "params": {"name": t["name"], "arguments": args}})
    for reply in rpc(vendor, calls):
        result = reply["result"]
        text = result["content"][0]["text"]
        assert result.get("isError") and "allow-write" in text, (reply["id"], text)
    assert not any(tmp_path.iterdir()), "nothing may be written without --allow-write"
