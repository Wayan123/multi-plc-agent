"""Client registration must add our one entry and leave everything else in the user's file intact."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

tomllib = __import__("tomllib") if sys.version_info >= (3, 11) else None
needs_toml = pytest.mark.skipif(tomllib is None, reason="tomllib needs Python 3.11+")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from multiplc import clients  # noqa: E402
from multiplc.clients import BY_KEY, SERVER  # noqa: E402


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData" / "Roaming"))
    return tmp_path


def register(key, project=None):
    lines = []
    assert clients.run("config.example.json", key, True, project, out=lines.append) == 0
    return lines


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


def test_vscode_uses_servers_key_in_the_project(home):
    register("vscode", str(home / "proj"))
    data = json.loads((home / "proj" / ".vscode" / "mcp.json").read_text(encoding="utf-8"))
    assert data["servers"][SERVER]["type"] == "stdio"


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
    assert clients.run("config.example.json", "claude-desktop", False, out=lines.append) == 0
    assert '"mcpServers"' in lines[0]
    assert not any(home.rglob("*.json"))
