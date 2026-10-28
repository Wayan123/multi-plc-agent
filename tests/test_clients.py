"""Client registration must add our one entry and leave everything else in the user's file intact."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

tomllib = __import__("tomllib") if sys.version_info >= (3, 11) else None
needs_toml = pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from multiplc import clients  # noqa: E402
from multiplc.clients import BY_KEY, SERVER  # noqa: E402

CONFIG = str(Path(__file__).resolve().parents[1] / "config.example.json")


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "AppData" / "Local"))
    return tmp_path


def register(key, project=None, scope="user"):
    lines = []
    assert clients.run(CONFIG, key, True, project, out=lines.append, scope=scope) == 0
    return lines


def test_every_client_has_a_documentation_source_and_vice_versa():
    sources = json.loads((Path(clients.__file__).with_name("client_sources.json")).read_text(encoding="utf-8"))
    assert set(sources["clients"]) == set(BY_KEY)
    assert all(s["url"].startswith("https://") and s["markers"] for s in sources["clients"].values())


@needs_toml
def test_codex_replaces_only_our_table_and_stays_valid_toml(home):
    path = home / ".codex" / "config.toml"
    path.parent.mkdir()
    path.write_text('model = "x"\n\n[mcp_servers.other]\ncommand = "a"\n\n'
                    f'[mcp_servers.{SERVER}]\ncommand = "old"\n[mcp_servers.{SERVER}.env]\nA = "1"\n\n'
                    '[profiles.p]\nk = 1\n', encoding="utf-8")
    register("codex")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    assert data["model"] == "x" and data["profiles"]["p"]["k"] == 1
    assert data["mcp_servers"]["other"] == {"command": "a"}
    ours = data["mcp_servers"][SERVER]
    assert ours["tool_timeout_sec"] == 900 and "env" not in ours and ours["command"] != "old"
    assert (path.parent / "config.toml.bak").read_text(encoding="utf-8").count('"old"') == 1


@needs_toml
def test_windows_paths_survive_toml(home, monkeypatch):
    monkeypatch.setattr(clients, "launch_command",
                        lambda config: (r"C:\PLC\venv\Scripts\python.exe", ["-m", "multiplc", "--config", r"C:\PLC\it's.json"]))
    register("codex")
    ours = tomllib.loads((home / ".codex" / "config.toml").read_text(encoding="utf-8"))["mcp_servers"][SERVER]
    assert ours["command"] == r"C:\PLC\venv\Scripts\python.exe"
    assert ours["args"][-1] == r"C:\PLC\it's.json"


@pytest.mark.parametrize("key", ["claude-code", "zcode", "gemini-cli", "copilot-cli"])
def test_json_merge_keeps_other_settings_and_is_idempotent(home, key):
    path = clients.resolve_path(BY_KEY[key])
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = {"numStartups": 5, "mcpServers": {"x": {"command": "y"}}, "mcp": {"servers": {"z": {"command": "w"}}}}
    path.write_text(json.dumps(existing), encoding="utf-8")
    register(key)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["numStartups"] == 5
    assert data["mcpServers"]["x"] == {"command": "y"} and data["mcp"]["servers"]["z"] == {"command": "w"}
    table = data["mcp"]["servers"] if key == "zcode" else data["mcpServers"]
    assert table[SERVER]["args"][:2] == ["-m", "multiplc"]
    before = path.read_text(encoding="utf-8")
    assert '"changed": false' in register(key)[0]
    assert path.read_text(encoding="utf-8") == before


def test_empty_file_is_treated_as_empty_config(home):
    path = clients.resolve_path(BY_KEY["antigravity"])
    path.parent.mkdir(parents=True)
    path.write_text("", encoding="utf-8")
    register("antigravity")
    assert json.loads(path.read_text(encoding="utf-8"))["mcpServers"][SERVER]["timeoutSeconds"] == 900


def test_vscode_user_and_project_scopes_use_the_servers_key(home):
    register("vscode")
    register("vscode", str(home / "proj"), scope="project")
    for path in (home / "AppData" / "Roaming" / "Code" / "User" / "mcp.json", home / "proj" / ".vscode" / "mcp.json"):
        assert json.loads(path.read_text(encoding="utf-8"))["servers"][SERVER]["type"] == "stdio"


@pytest.mark.parametrize("key,relative", [("cursor", ".cursor/mcp.json"), ("claude-code", ".mcp.json"),
                                          ("devin", ".devin/mcp_config.json"), ("antigravity", ".agents/mcp_config.json")])
def test_project_scope_writes_inside_the_project_only(home, key, relative):
    register(key, str(home / "proj"), scope="project")
    assert SERVER in json.loads((home / "proj" / relative).read_text(encoding="utf-8"))["mcpServers"]
    assert not clients.resolve_path(BY_KEY[key]).exists()


def test_project_scope_is_refused_where_the_client_has_none(home):
    with pytest.raises(ValueError, match="no project-level config"):
        register("claude-desktop", str(home / "proj"), scope="project")


def test_all_registers_only_installed_clients(home):
    (home / ".cursor").mkdir()
    (home / ".codex").mkdir()
    lines = register("all")
    written = {json.loads(line)["client"] for line in lines if line.startswith("{")}
    assert written == {"cursor", "codex"}
    assert not (home / ".gemini").exists() and not (home / ".zcode").exists()


def test_status_reports_registration_and_a_missing_interpreter(home, monkeypatch):
    register("cursor")
    out = []
    assert clients.run(CONFIG, "status", False, out=out.append) == 0
    rows = {r["client"]: r for r in json.loads(out[0])}
    assert rows["cursor"]["registered"] and rows["cursor"]["command_exists"]
    assert not rows["gemini-cli"]["registered"]
    path = clients.resolve_path(BY_KEY["cursor"])
    data = json.loads(path.read_text(encoding="utf-8"))
    data["mcpServers"][SERVER]["command"] = str(home / "gone" / "python.exe")
    path.write_text(json.dumps(data), encoding="utf-8")
    assert clients.run(CONFIG, "status", False, out=out.append) == 1


def test_claude_desktop_store_install_uses_the_packaged_folder(home):
    package = home / "AppData" / "Local" / "Packages" / "Claude_pzs8sxrjxfjjc"
    package.mkdir(parents=True)
    register("claude-desktop")
    target = home / "AppData" / "Local" / clients.CLAUDE_MSIX / "claude_desktop_config.json"
    assert SERVER in json.loads(target.read_text(encoding="utf-8"))["mcpServers"]
    assert not (home / "AppData" / "Roaming" / "Claude").exists()


def test_invalid_json_is_left_untouched(home):
    path = clients.resolve_path(BY_KEY["cursor"])
    path.parent.mkdir(parents=True)
    path.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError, match="nothing was changed"):
        register("cursor")
    assert path.read_text(encoding="utf-8") == "{bad"
    assert not path.with_name("mcp.json.bak").exists()


def test_print_writes_nothing(home):
    lines = []
    assert clients.run(CONFIG, "claude-desktop", False, out=lines.append) == 0
    assert '"mcpServers"' in lines[0]
    assert not any(home.rglob("*.json"))


@pytest.mark.parametrize("key", ["gemini-cli", "cursor"])
def test_written_entry_starts_the_server_from_another_folder(home, key):
    """Clients launch from their own folder; the entry alone must find the package (cwd or PYTHONPATH)."""
    import subprocess
    register(key)
    item = json.loads(clients.resolve_path(BY_KEY[key]).read_text(encoding="utf-8"))["mcpServers"][SERVER]
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"} | item.get("env", {})
    hello = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}})
    done = subprocess.run([item["command"], *item["args"]], input=hello + "\n", capture_output=True, text=True,
                          cwd=item.get("cwd", str(home)), env=env, timeout=60)
    assert '"serverInfo"' in done.stdout, done.stderr
