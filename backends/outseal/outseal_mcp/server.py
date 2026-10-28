"""MCP stdio server for Outseal Studio (Outseal PLC Nano / Mega).

The agent describes ladder as JSON. The server validates it per board, writes
an Outseal Studio .plc project file directly, and can compile it by driving
Outseal Studio's Test command (no hardware needed).

Rung JSON:
    {"comment": "Start/stop", "elements": [
        {"branch": [[{"kind": "NO", "args": ["S.1"], "note": "Start"}],
                    [{"kind": "NO", "args": ["R.1"]}]]},
        {"kind": "NC", "args": ["S.2"], "note": "Stop"},
        {"kind": "OUT", "args": ["R.1"], "note": "Motor"}]}
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

from . import __version__
from .codec import FormatError, Project, Rung, read_project, write_project
from .validate import ARITY, BOARDS, validate

PROTOCOL_VERSION = "2025-06-18"
GUI_SCRIPT = Path(__file__).with_name("outseal_gui.py")

ELEMENT_SCHEMA = {
    "type": "object",
    "description": "One instruction {kind, args[], note?} or a parallel branch {branch: [[elements...], ...]}",
}
RUNG_SCHEMA = {
    "type": "object",
    "properties": {
        "comment": {"type": "string"},
        "elements": {"type": "array", "items": ELEMENT_SCHEMA},
    },
    "required": ["elements"],
}
PROJECT_PROPS = {
    "name": {"type": "string"},
    "board": {"type": "string", "enum": sorted(BOARDS)},
    "main": {"type": "array", "items": RUNG_SCHEMA, "description": "Rungs of the Main diagram"},
    "initial": {"type": "array", "items": RUNG_SCHEMA, "description": "Rungs run once at start-up (Initial diagram)"},
    "aliases": {"type": "object", "additionalProperties": {"type": "string"},
                "description": "Symbol/comment per address, e.g. {\"S.1\": \"Start\"}"},
}

INSTRUCTIONS = (
    "Outseal Studio addresses are 1-based: inputs S.n, outputs R.n, internal bits B.n, integers I.n, "
    "timers T.n (bits .EN .TT .DN), counters C.n (.CU .CD .DN), analog A.n. Timer: "
    "{kind: TON, args: [T.1, <time base ms: 1000|100|10|1>, <preset>]} so [T.1, 1000, 3] is 3 s. "
    "Counter: {kind: CTU, args: [C.1, <preset>, <3rd field, use 0>]}. A rung ends with an output "
    "(OUT, OUTL/OUTU latch/unlatch, TON, CTU, RST, ...) or a branch whose legs each end with one. "
    "Call outseal_validate before outseal_write_project, then outseal_compile to run Outseal "
    "Studio's Test. outseal_compile reports compiler errors; it does not upload to a PLC."
)


def _tools() -> list[dict[str, Any]]:
    def schema(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
    return [
        {"name": "list_boards", "description": "Boards Outseal Studio can target, with digital input/output and analog input counts.",
         "inputSchema": schema({})},
        {"name": "instructions", "description": "Supported instruction names and their argument counts.",
         "inputSchema": schema({})},
        {"name": "validate", "description": "Check a project description (names, argument counts, address syntax and board I/O ranges) without writing anything.",
         "inputSchema": schema(PROJECT_PROPS, ["name", "board", "main"])},
        {"name": "write_project", "description": "Validate, then write an Outseal Studio .plc file. Refuses on validation errors. Existing files are backed up to <file>.bak unless overwrite is false (then it refuses).",
         "inputSchema": schema({**PROJECT_PROPS, "path": {"type": "string", "description": "Target .plc path"},
                                "overwrite": {"type": "boolean", "default": False}}, ["path", "name", "board", "main"])},
        {"name": "read_project", "description": "Read an Outseal Studio .plc file as JSON (same shape as outseal_write_project).",
         "inputSchema": schema({"path": {"type": "string"}}, ["path"])},
        {"name": "compile", "description": "Open a .plc in Outseal Studio and run Test (compile, no hardware). Returns ok, error_count, errors and the generated hex size. Uses the desktop: one call at a time.",
         "inputSchema": schema({"path": {"type": "string"}, "keep_open": {"type": "boolean", "default": True}}, ["path"])},
    ]


def _project_from_args(args: dict[str, Any]) -> Project:
    return Project.from_json({"name": args["name"], "hardware": args["board"], "main": args.get("main", []),
                              "initial": args.get("initial", []), "aliases": args.get("aliases", {})})


class Server:
    def __init__(self, gui_python: str | None, outseal_exe: str | None, allow_write: bool):
        self.gui_python = gui_python
        self.outseal_exe = outseal_exe
        self.allow_write = allow_write
        self._gui_lock = threading.Lock()

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_boards":
            return {"boards": [{"name": k, "digital_inputs": v[0], "digital_outputs": v[1], "analog_inputs": v[2]}
                               for k, v in BOARDS.items()]}
        if name == "instructions":
            return {"instructions": ARITY}
        if name == "validate":
            findings = validate(_project_from_args(args))
            return {"ok": not any(f.level == "error" for f in findings), "findings": [f.to_json() for f in findings]}
        if name == "write_project":
            if not self.allow_write:
                raise PermissionError("writing is disabled; start the server with --allow-write")
            project = _project_from_args(args)
            findings = validate(project)
            if any(f.level == "error" for f in findings):
                return {"ok": False, "written": False, "findings": [f.to_json() for f in findings]}
            path = Path(args["path"])
            if path.suffix.lower() != ".plc":
                raise ValueError("path must end with .plc")
            backup = None
            if path.exists():
                if not args.get("overwrite", False):
                    raise FileExistsError(f"{path} exists; pass overwrite=true to replace it (a .bak copy is kept)")
                backup = str(path) + ".bak"
                shutil.copy2(path, backup)
            path.parent.mkdir(parents=True, exist_ok=True)
            write_project(path, project)
            reread = read_project(path)
            if reread.to_json() != project.to_json():
                raise FormatError("written file does not read back identically")
            return {"ok": True, "written": True, "path": str(path.resolve()), "backup": backup,
                    "rungs": len(project.main), "findings": [f.to_json() for f in findings]}
        if name == "read_project":
            return read_project(args["path"]).to_json()
        if name == "compile":
            return self._compile(args["path"], args.get("keep_open", True))
        raise KeyError(f"unknown tool {name!r}")

    def _compile(self, path: str, keep_open: bool) -> dict[str, Any]:
        if not self.gui_python:
            raise RuntimeError("outseal_compile needs --gui-python (Windows Python with pywinauto)")
        command = [self.gui_python, str(GUI_SCRIPT), "compile", str(Path(path).resolve())]
        if self.outseal_exe:
            command += ["--exe", self.outseal_exe]
        if keep_open:
            command.append("--keep-open")
        with self._gui_lock:
            done = subprocess.run(command, capture_output=True, text=True, timeout=300)
        lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
        if not lines:
            return {"ok": False, "error": "GUI driver printed no result", "stderr": done.stderr[-800:]}
        return json.loads(lines[-1])


def _result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
    if is_error:
        out["isError"] = True
    return out


def serve(server: Server) -> None:
    stdin = open(sys.stdin.fileno(), encoding="utf-8", closefd=False)
    write_lock = threading.Lock()

    def write(message: dict[str, Any]) -> None:
        with write_lock:
            sys.stdout.buffer.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
            sys.stdout.buffer.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        if "id" not in message:
            continue
        method, params, rid = message.get("method"), message.get("params") or {}, message["id"]
        if method == "initialize":
            write({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "outseal-mcp", "version": __version__},
                "instructions": INSTRUCTIONS}})
        elif method == "ping":
            write({"jsonrpc": "2.0", "id": rid, "result": {}})
        elif method == "tools/list":
            write({"jsonrpc": "2.0", "id": rid, "result": {"tools": _tools()}})
        elif method == "tools/call":
            try:
                payload = server.call(params.get("name"), params.get("arguments") or {})
                write({"jsonrpc": "2.0", "id": rid, "result": _result(payload)})
            except Exception as error:
                write({"jsonrpc": "2.0", "id": rid, "result": _result({"error": f"{type(error).__name__}: {error}"}, True)})
        else:
            write({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="outseal-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--allow-write", action="store_true", help="enable outseal_write_project")
    parser.add_argument("--gui-python", default=os.environ.get("OUTSEAL_GUI_PYTHON"),
                        help="Windows python.exe with pywinauto, used by outseal_compile")
    parser.add_argument("--outseal-exe", default=os.environ.get("OUTSEAL_EXE"))
    args = parser.parse_args(argv)
    serve(Server(args.gui_python, args.outseal_exe, args.allow_write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
