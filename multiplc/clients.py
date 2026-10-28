"""MCP client registration: one table of client formats, rendered or merged into the client's file.

    multi-plc-agent --config C:\\plc\\config.json --client list
    multi-plc-agent --config C:\\plc\\config.json --client claude-code          # print the snippet
    multi-plc-agent --config C:\\plc\\config.json --client claude-code --client-write   # merge into the file

Formats follow each vendor's documentation (see docs/clients.md, checked 2026-10-28).
--client-write merges our one entry into the existing file, keeps every other
setting, and saves the previous file as <file>.bak. It never deletes entries.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SERVER = "multi-plc"
TOOL_TIMEOUT_S = 900  # GUI-driven backends need up to ~15 minutes per call


@dataclass(frozen=True)
class Client:
    key: str
    title: str
    # path relative to a scope root; "~" = user home, "%APPDATA%" = roaming app data, "." = project
    path: str
    shape: str  # "servers" | "mcpServers" | "codex-toml" | "zcode"
    extra: dict[str, Any] = field(default_factory=dict)  # fields added to our entry
    cwd: bool = False  # client documents a working-directory key
    cli: str = ""  # vendor CLI command doing the same, for the docs/print
    note: str = ""


CLIENTS: list[Client] = [
    Client("vscode", "VS Code (GitHub Copilot agent mode), workspace", "./.vscode/mcp.json", "servers",
           {"type": "stdio"}, cwd=True, cli="code --add-mcp '<json>'  (user profile)",
           note="No documented per-tool timeout. User-profile file: run 'MCP: Open User Configuration'."),
    Client("copilot-cli", "GitHub Copilot CLI", "~/.copilot/mcp-config.json", "mcpServers",
           {"type": "local", "tools": ["*"], "timeout": TOOL_TIMEOUT_S * 1000}, cwd=True,
           cli=f"copilot mcp add {SERVER} --timeout {TOOL_TIMEOUT_S * 1000} -- <command> <args>"),
    Client("codex", "OpenAI Codex (CLI, IDE extension, desktop app)", "~/.codex/config.toml", "codex-toml",
           {"startup_timeout_sec": 60, "tool_timeout_sec": TOOL_TIMEOUT_S}, cwd=True,
           cli=f"codex mcp add {SERVER} -- <command> <args>  (then add tool_timeout_sec)"),
    Client("cursor", "Cursor IDE and Cursor CLI (cursor-agent)", "~/.cursor/mcp.json", "mcpServers",
           {"type": "stdio"},
           note="Cursor CLI ends tool calls after 60 s (not configurable); use the IDE for GUI backends."),
    Client("devin", "Devin Desktop (Devin Local, Cascade) and Devin CLI", "%APPDATA%/devin/mcp_config.json",
           "mcpServers", cli=f"devin mcp add -s user {SERVER} -- <command> <args>",
           note="Devin cloud runs stdio servers in its own VM and can't reach PLC software on your PC; see docs/clients.md."),
    Client("zcode", "Z.ai ZCode", "~/.zcode/cli/config.json", "zcode",
           note="ZCode's GUI: Settings > MCP Servers. No timeout key is documented."),
    Client("claude-desktop", "Claude Desktop", "%APPDATA%/Claude/claude_desktop_config.json", "mcpServers",
           note="MSIX installs read %LOCALAPPDATA%/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/ instead. Restart Claude after writing."),
    Client("claude-code", "Claude Code (CLI, VS Code and JetBrains extensions), user scope", "~/.claude.json",
           "mcpServers", {"type": "stdio", "timeout": TOOL_TIMEOUT_S * 1000},
           cli=f"claude mcp add-json -s user {SERVER} '<json>'"),
    Client("antigravity", "Google Antigravity (App, IDE, CLI)", "~/.gemini/config/mcp_config.json", "mcpServers",
           {"timeoutSeconds": TOOL_TIMEOUT_S}, cwd=True),
    Client("gemini-cli", "Gemini CLI", "~/.gemini/settings.json", "mcpServers",
           {"timeout": TOOL_TIMEOUT_S * 1000}, cwd=True,
           cli=f"gemini mcp add -s user --timeout {TOOL_TIMEOUT_S * 1000} {SERVER} <command> -- <args>"),
]
BY_KEY = {c.key: c for c in CLIENTS}


def launch_command(config: str) -> tuple[str, list[str]]:
    """Absolute command for this installation: the interpreter running us plus -m multiplc."""
    return sys.executable, ["-m", "multiplc", "--config", str(Path(config).resolve())]


def entry(client: Client, command: str, args: list[str], cwd: str | None) -> dict[str, Any]:
    item: dict[str, Any] = {"command": command, "args": list(args)}
    if cwd and client.cwd:
        item["cwd"] = cwd
    item.update(client.extra)
    return item


def resolve_path(client: Client, project: Path | None = None) -> Path:
    raw = client.path
    if raw.startswith("./"):
        return (project or Path.cwd()) / raw[2:]
    if raw.startswith("%APPDATA%/"):
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / raw[len("%APPDATA%/"):]
    return Path(os.path.expanduser(raw))


# --- rendering and merging ------------------------------------------------------

def _toml_str(value: str) -> str:
    if "'" not in value and "\n" not in value:
        return f"'{value}'"  # literal string: Windows backslashes stay as they are
    return json.dumps(value)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    return _toml_str(str(value))


def codex_block(item: dict[str, Any]) -> str:
    lines = [f"[mcp_servers.{SERVER}]"]
    for key, value in item.items():
        lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def merge_codex(text: str, item: dict[str, Any]) -> str:
    """Replace our [mcp_servers.multi-plc] table (and its sub-tables) or append it."""
    head = f"[mcp_servers.{SERVER}]"
    out, skipping, replaced = [], False, False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            is_ours = stripped == head or stripped.startswith(f"[mcp_servers.{SERVER}.")
            if is_ours:
                if not replaced:
                    out.append(codex_block(item) + "\n")
                    replaced = True
                skipping = True
                continue
            skipping = False
        if not skipping:
            out.append(line)
    result = "".join(out)
    if not replaced:
        result = result.rstrip("\n") + ("\n\n" if result.strip() else "") + codex_block(item)
    return result


def merge_json(data: dict[str, Any], client: Client, item: dict[str, Any]) -> dict[str, Any]:
    if client.shape == "zcode":
        data.setdefault("mcp", {}).setdefault("servers", {})[SERVER] = item
    else:
        data.setdefault(client.shape, {})[SERVER] = item
    return data


def render(client: Client, item: dict[str, Any]) -> str:
    if client.shape == "codex-toml":
        return codex_block(item)
    return json.dumps(merge_json({}, client, item), indent=2) + "\n"


def write(client: Client, item: dict[str, Any], path: Path) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    old = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    backup = None
    if client.shape == "codex-toml":
        new = merge_codex(old, item)
    else:
        try:
            data = json.loads(old) if old.strip() else {}
        except ValueError as error:
            raise ValueError(f"{path} is not valid JSON ({error}); fix or move it first, nothing was changed") from error
        if not isinstance(data, dict):
            raise ValueError(f"{path} does not hold a JSON object; nothing was changed")
        new = json.dumps(merge_json(data, client, item), indent=2, ensure_ascii=False) + "\n"
    if old == new:
        return {"path": str(path), "changed": False, "backup": None}
    if path.exists():
        backup = str(path) + ".bak"
        shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, path)
    return {"path": str(path), "changed": True, "backup": backup}


def run(config: str, client_key: str, do_write: bool, project: str | None = None,
        out: Callable[[str], None] = print) -> int:
    if client_key == "list":
        for c in CLIENTS:
            out(f"{c.key:15} {c.title}  ->  {resolve_path(c, Path(project) if project else None)}")
        return 0
    client = BY_KEY.get(client_key)
    if client is None:
        out(f"unknown client {client_key!r}; one of: {', '.join(BY_KEY)} (or 'list')")
        return 2
    command, args = launch_command(config)
    item = entry(client, command, args, str(Path(config).resolve().parent))
    path = resolve_path(client, Path(project) if project else None)
    if not do_write:
        out(f"# {client.title}\n# file: {path}\n" + (f"# note: {client.note}\n" if client.note else "") + render(client, item))
        return 0
    result = write(client, item, path)
    out(json.dumps({"client": client.key, **result}, ensure_ascii=False))
    if client.note:
        out(f"note: {client.note}")
    return 0
