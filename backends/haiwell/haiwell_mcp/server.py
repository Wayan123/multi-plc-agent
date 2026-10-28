"""MCP stdio server for Haiwell Happy (Haiwell PLC C/T/N/H series).

Haiwell Happy has no ladder import, so write_ladder types the rungs into the LD
editor with the program's documented shortcuts and then verifies the result by
exporting IL and comparing it with the IL the rung JSON implies. Component
comments go through the same entry ("X0//Start"). Everything runs offline on
a project copy; nothing is downloaded to a PLC.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from . import __version__
from .ladder import OUTPUTS, expected_il, il_text, parse_il, plan, validate

PROTOCOL_VERSION = "2025-06-18"
GUI_SCRIPT = Path(__file__).with_name("haiwell_gui.py")
TEMPLATES = Path(__file__).with_name("templates")

RUNG_SCHEMA = {
    "type": "object",
    "properties": {
        "comment": {"type": "string"},
        "elements": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["elements"],
}
LADDER_PROPS = {
    "rungs": {"type": "array", "items": RUNG_SCHEMA},
    "aliases": {"type": "object", "additionalProperties": {"type": "string"},
                "description": "Component comment per address, e.g. {\"X0\": \"Start PB\"}"},
}

INSTRUCTIONS = (
    "Haiwell addresses: inputs X0.., outputs Y0.., internal relays M0.., timers T0.., counters C0... "
    "Rung elements: contacts {kind: NO|NC, args: [addr], note?}, parallel {branch: [[contact], [contact, ...], ...]} "
    "(first leg exactly one contact, no nesting), then exactly one output: OUT [coil], SET [bit], RST [target], "
    "TON [Tn, preset in seconds] (1 s time base), CTU [Cn, preset]. Call haiwell_validate, then "
    "haiwell_write_ladder (replaces the first program block, saves, and checks the IL read-back), then "
    "haiwell_compile. The desktop is used for typing: one call at a time and do not touch the keyboard."
)


def _tools() -> list[dict[str, Any]]:
    def schema(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
    return [
        {"name": "list_templates", "description": "Project templates (CPU models) new_project can copy.",
         "inputSchema": schema({})},
        {"name": "new_project", "description": "Create a .gpc project from a template (one empty LD block MainLD). Refuses to overwrite.",
         "inputSchema": schema({"path": {"type": "string"}, "template": {"type": "string"}}, ["path"])},
        {"name": "validate", "description": "Check rungs against what the keystroke writer supports and return the expected IL. Writes nothing.",
         "inputSchema": schema(LADDER_PROPS, ["rungs"])},
        {"name": "write_ladder", "description": "Replace the first program block of a .gpc with the rungs by typing them into Haiwell Happy, save, export IL and compare it with the expected IL. A .bak copy of the project is kept.",
         "inputSchema": schema({**LADDER_PROPS, "path": {"type": "string"}}, ["path", "rungs"])},
        {"name": "export_il", "description": "Open a .gpc in Haiwell Happy and return its program as IL text (Tools > Convert program to IL).",
         "inputSchema": schema({"path": {"type": "string"}}, ["path"])},
        {"name": "compile", "description": "Open a .gpc in Haiwell Happy and run Debug > Compile. Returns error/warning counts and messages.",
         "inputSchema": schema({"path": {"type": "string"}}, ["path"])},
    ]


class Server:
    def __init__(self, gui_python: str | None, exe: str | None, allow_write: bool):
        self.gui_python = gui_python
        self.exe = exe
        self.allow_write = allow_write
        self._gui_lock = threading.Lock()

    def _gui(self, job: dict[str, Any]) -> dict[str, Any]:
        if not self.gui_python:
            raise RuntimeError("this tool needs --gui-python (Windows Python with pywinauto and pywin32)")
        if self.exe:
            job["exe"] = self.exe
        fd, job_path = tempfile.mkstemp(suffix=".json", prefix="haiwell_job_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(job, f)
        try:
            with self._gui_lock:
                done = subprocess.run([self.gui_python, str(GUI_SCRIPT), _win_path(job_path)],
                                      capture_output=True, text=True, timeout=900)
        finally:
            os.unlink(job_path)
        lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
        if not lines:
            return {"ok": False, "error": "GUI driver printed no result", "stderr": done.stderr[-800:]}
        return json.loads(lines[-1])

    def _writable(self, path: str) -> Path:
        if not self.allow_write:
            raise PermissionError("writing is disabled; start the server with --allow-write")
        p = Path(path)
        if p.suffix.lower() != ".gpc":
            raise ValueError("path must end with .gpc")
        return p

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_templates":
            return {"templates": sorted(p.stem for p in TEMPLATES.glob("*.gpc")),
                    "note": "Other CPUs: create the project in Haiwell Happy (File > New) and pass its path."}
        if name == "new_project":
            dest = self._writable(args["path"])
            template = TEMPLATES / f"{args.get('template') or 'AT16S0T'}.gpc"
            if not template.exists():
                raise FileNotFoundError(f"unknown template {template.stem!r}")
            if dest.exists():
                raise FileExistsError(f"{dest} exists")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template, dest)
            return {"ok": True, "path": str(dest.resolve()), "template": template.stem, "block": "MainLD"}
        rungs, aliases = args.get("rungs", []), args.get("aliases") or {}
        if name == "validate":
            findings = validate(rungs, aliases)
            ok = not findings
            return {"ok": ok, "findings": [f.to_json() for f in findings],
                    "expected_il": il_text(expected_il(rungs)) if ok else None}
        if name == "write_ladder":
            path = self._writable(args["path"])
            if not path.exists():
                raise FileNotFoundError(f"{path} does not exist; use new_project first")
            findings = validate(rungs, aliases)
            if findings:
                return {"ok": False, "written": False, "findings": [f.to_json() for f in findings]}
            keyplan = plan(rungs, aliases)
            backup = str(path) + ".bak"
            shutil.copy2(path, backup)
            result = self._gui({"op": "write", "path": _win_path(str(path.resolve())), "steps": keyplan["steps"]})
            if "il" in result:
                block = result.get("block", "PGB:MainLD").removeprefix("PGB:")
                got, want = parse_il(result.pop("il"), block), expected_il(rungs)
                result["il_matches"] = got == want
                result["il"] = il_text(got)
                if got != want:
                    result["ok"] = False
                    result["expected_il"] = il_text(want)
            result.update({"backup": backup, "rungs": len(rungs),
                           "aliases_not_used_in_ladder": sorted(keyplan["unapplied_aliases"])})
            return result
        if name == "export_il":
            result = self._gui({"op": "export_il", "path": _win_path(str(Path(args["path"]).resolve()))})
            return result
        if name == "compile":
            return self._gui({"op": "compile", "path": _win_path(str(Path(args["path"]).resolve()))})
        raise KeyError(f"unknown tool {name!r}")


def _win_path(path: str) -> str:
    """WSL /mnt/<d>/... -> D:\\...; Windows paths pass through."""
    if path.startswith("/mnt/") and len(path) > 6 and path[6] == "/":
        return f"{path[5].upper()}:\\" + path[7:].replace("/", "\\")
    return path


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
                "serverInfo": {"name": "haiwell-mcp", "version": __version__},
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
    parser = argparse.ArgumentParser(prog="haiwell-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--allow-write", action="store_true", help="enable new_project and write_ladder")
    parser.add_argument("--gui-python", default=os.environ.get("HAIWELL_GUI_PYTHON"),
                        help="Windows python.exe with pywinauto and pywin32")
    parser.add_argument("--haiwell-exe", default=os.environ.get("HAIWELL_EXE"))
    args = parser.parse_args(argv)
    serve(Server(args.gui_python, args.haiwell_exe, args.allow_write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
