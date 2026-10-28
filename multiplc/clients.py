"""MCP client registration: one table of client formats, rendered or merged into the client's file.

    multi-plc-agent --config C:\\plc\\config.json --client list            # clients, files, installed or not
    multi-plc-agent --config C:\\plc\\config.json --client status          # where multi-plc is registered
    multi-plc-agent --config C:\\plc\\config.json --client codex           # print the entry, change nothing
    multi-plc-agent --config C:\\plc\\config.json --client codex --client-write
    multi-plc-agent --config C:\\plc\\config.json --client all --client-write    # every installed client
    multi-plc-agent --config C:\\plc\\config.json --client cursor --scope project --project C:\\work\\line1 --client-write

Formats follow each vendor's documentation (docs/clients.md lists the sources and the date
they were checked; .github/workflows/client-docs.yml re-checks the sources monthly).
--client-write merges our one entry into the existing file, keeps every other setting,
and saves the previous file as <file>.bak. It never deletes entries.
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
CLAUDE_MSIX = "Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude"


@dataclass(frozen=True)
class Client:
    key: str
    title: str
    surfaces: str  # which apps read this file: IDE, CLI, desktop app
    user: str  # user-scope file: "~/..." home, "%APPDATA%/..." app data (Windows) or its equivalent
    project: str  # project-scope file relative to the project folder; "" = no project scope
    shape: str  # "servers" | "mcpServers" | "codex-toml" | "zcode"
    extra: dict[str, Any] = field(default_factory=dict)  # fields added to our entry
    cwd: bool = False  # client documents a working-directory key
    detect: str = ""  # path whose existence means "installed"; default: the user file's folder
    note: str = ""


CLIENTS: list[Client] = [
    Client("vscode", "VS Code with GitHub Copilot (agent mode)", "IDE",
           "%APPDATA%/Code/User/mcp.json", ".vscode/mcp.json", "servers", {"type": "stdio"}, cwd=True,
           detect="%APPDATA%/Code/User",
           note="No documented per-tool timeout. Reload the window or run 'MCP: List Servers' to start it."),
    Client("copilot-cli", "GitHub Copilot CLI", "CLI",
           "~/.copilot/mcp-config.json", ".github/mcp.json", "mcpServers",
           {"type": "local", "tools": ["*"], "timeout": TOOL_TIMEOUT_S * 1000}, cwd=True),
    Client("codex", "OpenAI Codex", "CLI, IDE extension (VS Code, Cursor, JetBrains), desktop app",
           "~/.codex/config.toml", ".codex/config.toml", "codex-toml",
           {"startup_timeout_sec": 60, "tool_timeout_sec": TOOL_TIMEOUT_S}, cwd=True,
           note="Codex reads a project .codex/config.toml only in trusted projects."),
    Client("cursor", "Cursor", "IDE and CLI (cursor-agent)",
           "~/.cursor/mcp.json", ".cursor/mcp.json", "mcpServers", {"type": "stdio"},
           note="Cursor CLI ends tool calls after 60 s (not configurable); use the Cursor IDE for GUI backends."),
    Client("devin", "Devin (Devin Desktop: Devin Local and Cascade; Devin CLI)", "desktop IDE and CLI",
           "%APPDATA%/devin/mcp_config.json", ".devin/mcp_config.json", "mcpServers",
           note="Devin cloud runs stdio servers in its own VM and can't reach PLC software on your PC; see docs/clients.md."),
    Client("zcode", "Z.ai ZCode", "desktop app",
           "~/.zcode/cli/config.json", ".zcode/config.json", "zcode", detect="~/.zcode",
           note="No timeout key is documented. ZCode GUI: Settings > MCP Servers."),
    Client("claude-desktop", "Claude Desktop", "desktop app",
           "%APPDATA%/Claude/claude_desktop_config.json", "", "mcpServers",
           note="Quit Claude from the tray and start it again after writing."),
    Client("claude-code", "Claude Code", "CLI, VS Code and JetBrains extensions, Claude desktop Code tab",
           "~/.claude.json", ".mcp.json", "mcpServers", {"type": "stdio", "timeout": TOOL_TIMEOUT_S * 1000},
           detect="~/.claude",
           note="A project .mcp.json asks each user for approval on first use."),
    Client("antigravity", "Google Antigravity", "app, IDE and CLI",
           "~/.gemini/config/mcp_config.json", ".agents/mcp_config.json", "mcpServers",
           {"timeoutSeconds": TOOL_TIMEOUT_S}, cwd=True, detect="~/.gemini/config"),
    Client("gemini-cli", "Gemini CLI", "CLI",
           "~/.gemini/settings.json", ".gemini/settings.json", "mcpServers",
           {"timeout": TOOL_TIMEOUT_S * 1000}, cwd=True, detect="~/.gemini/settings.json",
           note="User-level servers stay disabled in folders you haven't trusted."),
]
BY_KEY = {c.key: c for c in CLIENTS}


def launch_command(config: str) -> tuple[str, list[str]]:
    """Absolute command for this installation: the interpreter running us plus -m multiplc."""
    return sys.executable, ["-m", "multiplc", "--config", str(Path(config).resolve())]


def source_checkout() -> str | None:
    """The folder holding multiplc/ when it runs from a checkout instead of an installed package.

    Clients start the server from their own working directory, so `-m multiplc` only works from a
    checkout if PYTHONPATH points at it.
    """
    import sysconfig
    here = Path(__file__).resolve().parent.parent
    installed_dirs = {Path(sysconfig.get_paths()[k]).resolve() for k in ("purelib", "platlib")}
    return None if here in installed_dirs else str(here)


def entry(client: Client, command: str, args: list[str], cwd: str | None) -> dict[str, Any]:
    item: dict[str, Any] = {"command": command, "args": list(args)}
    checkout = source_checkout()
    if client.cwd:
        # `python -m` finds the package in its working directory; some clients (Gemini CLI)
        # refuse a PYTHONPATH override, so a checkout is reached through cwd where possible.
        if checkout or cwd:
            item["cwd"] = checkout or cwd
    elif checkout:
        item["env"] = {"PYTHONPATH": checkout}
    item.update(client.extra)
    return item


def _app_data() -> Path:
    """%APPDATA% on Windows; the matching per-user folder elsewhere (VS Code, Devin use it)."""
    if os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"])
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _expand(raw: str) -> Path:
    if raw.startswith("%APPDATA%/"):
        return _app_data() / raw[len("%APPDATA%/"):]
    return Path(os.path.expanduser(raw))


def resolve_path(client: Client, scope: str = "user", project: Path | None = None) -> Path:
    if scope == "project":
        if not client.project:
            raise ValueError(f"{client.title} has no project-level config; use --scope user")
        return (project or Path.cwd()) / client.project
    if client.key == "claude-desktop":
        # Microsoft Store (MSIX) installs read a virtualised copy of %APPDATA%\Claude.
        local = os.environ.get("LOCALAPPDATA")
        if local and (Path(local) / CLAUDE_MSIX.split("/LocalCache")[0]).is_dir():
            return Path(local) / CLAUDE_MSIX / "claude_desktop_config.json"
    return _expand(client.user)


def installed(client: Client) -> bool:
    return _expand(client.detect).exists() if client.detect else resolve_path(client).parent.is_dir()


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
    if isinstance(value, dict):
        return "{ " + ", ".join(f"{json.dumps(k)} = {_toml_value(v)}" for k, v in value.items()) + " }"
    return _toml_str(str(value))


def codex_block(item: dict[str, Any]) -> str:
    lines = [f"[mcp_servers.{SERVER}]"]
    for key, value in item.items():
        lines.append(f"{key} = {_toml_value(value)}")
    return "\n".join(lines) + "\n"


def _is_our_table(stripped: str) -> bool:
    return stripped == f"[mcp_servers.{SERVER}]" or stripped.startswith(f"[mcp_servers.{SERVER}.")


def merge_codex(text: str, item: dict[str, Any]) -> str:
    """Replace our [mcp_servers.multi-plc] table (and its sub-tables) or append it."""
    out, skipping, replaced = [], False, False
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("["):
            if _is_our_table(stripped):
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


def _table(data: dict[str, Any], client: Client) -> dict[str, Any] | None:
    found = data.get("mcp", {}).get("servers") if client.shape == "zcode" else data.get(client.shape)
    return found if isinstance(found, dict) else None


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


def _load_json(path: Path, text: str) -> dict[str, Any]:
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError as error:
        raise ValueError(f"{path} is not valid JSON ({error}); fix or move it first, nothing was changed") from error
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not hold a JSON object; nothing was changed")
    return data


def write(client: Client, item: dict[str, Any], path: Path) -> dict[str, Any]:
    old = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    if client.shape == "codex-toml":
        new = merge_codex(old, item)
    else:
        new = json.dumps(merge_json(_load_json(path, old), client, item), indent=2, ensure_ascii=False) + "\n"
    if old == new:
        return {"path": str(path), "changed": False, "backup": None}
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        backup = str(path) + ".bak"
        shutil.copy2(path, backup)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(new, encoding="utf-8")
    os.replace(tmp, path)
    return {"path": str(path), "changed": True, "backup": backup}


def registered(client: Client, path: Path) -> dict[str, Any] | None:
    """Our entry as stored in the client's file, or None. Codex: only whether the table exists."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8-sig")
    if client.shape == "codex-toml":
        try:
            import tomllib
        except ImportError:  # Python 3.10
            return {} if any(_is_our_table(line.strip()) for line in text.splitlines()) else None
        return tomllib.loads(text).get("mcp_servers", {}).get(SERVER)
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        return None
    table = _table(data, client) if isinstance(data, dict) else None
    return table.get(SERVER) if table else None


# --- command line ---------------------------------------------------------------

def _status_row(client: Client, scope: str, project: Path | None) -> dict[str, Any]:
    path = resolve_path(client, scope, project)
    found = registered(client, path)
    row: dict[str, Any] = {"client": client.key, "scope": scope, "path": str(path), "registered": found is not None}
    if found:
        command = found.get("command", "")
        row["command"] = command
        row["command_exists"] = bool(command) and (Path(command).exists() or shutil.which(command) is not None)
    return row


def run(config: str, client_key: str, do_write: bool, project: str | None = None,
        out: Callable[[str], None] = print, scope: str = "user") -> int:
    proj = Path(project).resolve() if project else None
    if client_key == "list":
        for c in CLIENTS:
            mark = "installed" if installed(c) else "not found"
            out(f"{c.key:15} {mark:10} {c.title} [{c.surfaces}]")
            out(f"{'':27}user:    {resolve_path(c)}")
            if c.project:
                out(f"{'':27}project: {resolve_path(c, 'project', proj)}")
        return 0
    if client_key == "status":
        rows = [_status_row(c, "user", None) for c in CLIENTS]
        if proj:
            rows += [_status_row(c, "project", proj) for c in CLIENTS if c.project]
        out(json.dumps(rows, ensure_ascii=False, indent=2))
        stale = [r for r in rows if r["registered"] and not r.get("command_exists", True)]
        return 1 if stale else 0
    if client_key == "all":
        targets = [c for c in CLIENTS if (c.project if scope == "project" else installed(c))]
        if not targets:
            out("no supported client found on this machine; run --client list")
            return 1
    elif client_key in BY_KEY:
        targets = [BY_KEY[client_key]]
    else:
        out(f"unknown client {client_key!r}; one of: {', '.join(BY_KEY)} (or list, status, all)")
        return 2
    command, args = launch_command(config)
    cwd = str(Path(config).resolve().parent)
    for client in targets:
        item = entry(client, command, args, cwd)
        path = resolve_path(client, scope, proj)
        if not do_write:
            out(f"# {client.title} [{client.surfaces}], {scope} scope\n# file: {path}\n"
                + (f"# note: {client.note}\n" if client.note else "") + render(client, item))
            continue
        result = write(client, item, path)
        out(json.dumps({"client": client.key, "scope": scope, **result}, ensure_ascii=False))
        if client.note:
            out(f"note: {client.note}")
    if do_write and scope == "project":
        out("note: project files hold absolute paths of this PC; keep them out of version control "
            "or replace the paths before committing.")
    return 0
