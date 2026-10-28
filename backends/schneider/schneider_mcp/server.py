"""MCP stdio server for EcoStruxure Machine Expert - Basic (Modicon M221).

The agent describes ladder as JSON. The server validates it against the
controller in the project, writes the rungs as IL into a Machine Expert - Basic
.smbp project file (a plain XML document without checksums), and can open the
file in Machine Expert - Basic to compile it, optionally converting every rung
to ladder there (no PLC connection).

Rung JSON:
    {"comment": "Run request", "elements": [
        {"branch": [[{"kind": "NO", "args": ["%I0.0"], "note": "Start"}],
                    [{"kind": "NO", "args": ["%M0"]}]]},
        {"kind": "NC", "args": ["%I0.1"], "note": "Stop"},
        {"kind": "OUT", "args": ["%M0"], "note": "Run"}]}
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
from .codec import (DEFAULT_TEMPLATE, KINDS, TEMPLATES, FormatError, compare, expected_il, limits_of,
                    normalize_il, parse, read_project, read_text, validate, win_path, write_project)

PROTOCOL_VERSION = "2025-06-18"
GUI_SCRIPT = Path(__file__).with_name("schneider_gui.py")

ELEMENT_SCHEMA = {
    "type": "object",
    "description": "One instruction {kind, args[], note?} or a parallel branch {branch: [[elements...], ...]}",
}
RUNG_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "comment": {"type": "string"},
        "elements": {"type": "array", "items": ELEMENT_SCHEMA},
    },
    "required": ["elements"],
}
LADDER_PROPS = {
    "rungs": {"type": "array", "items": RUNG_SCHEMA, "description": "Rungs of the first POU (Master Task)"},
    "symbols": {"type": "object", "additionalProperties": {"type": "string"},
                "description": "Symbol per address, e.g. {\"%I0.0\": \"START_PB\"}"},
}

INSTRUCTIONS = (
    "Machine Expert - Basic (Modicon M221) addresses: inputs %I0.n, outputs %Q0.n, memory bits %Mn, "
    "system bits %Sn, timer done bit %TMn.Q, counter done bit %Cn.D (also .E empty, .F full). "
    "Contacts NO, NC, RE (rising edge), FE (falling edge); outputs OUT, OUTN (negated), SET, RST; "
    "several outputs may end one rung. Timer: {kind: TON|TOF|TP, args: [%TMn, preset, base]} with base "
    "1ms|10ms|100ms|1s|1min (default 1s), so [%TM0, 3, 1s] is 3 s; use %TMn.Q in later rungs. Counter: "
    "{kind: CTU, args: [%Cn, preset, reset_bit?]}; use %Cn.D in later rungs. A timer or counter is the only "
    "output of its rung. Use new_project, then write_program (validates, writes IL, reads it back), then "
    "compile to check it in Machine Expert - Basic (to_ladder=true also converts the rungs to ladder and "
    "saves). Nothing is downloaded to a controller."
)


def _tools() -> list[dict[str, Any]]:
    def schema(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
    path = {"path": {"type": "string", "description": "Project .smbp path"}}
    return [
        {"name": "list_templates", "description": "Controllers available for new_project (empty projects saved from Machine Expert - Basic).",
         "inputSchema": schema({})},
        {"name": "instructions", "description": "Supported element kinds and their arguments.",
         "inputSchema": schema({})},
        {"name": "new_project", "description": "Create an empty .smbp from a bundled template. Refuses to overwrite.",
         "inputSchema": schema({**path, "template": {"type": "string", "default": DEFAULT_TEMPLATE}}, ["path"])},
        {"name": "validate", "description": "Check rungs (element kinds, argument counts, M221 address syntax and, with path, the controller's I/O range) and return the IL that would be written. Writes nothing.",
         "inputSchema": schema({**LADDER_PROPS, **path}, ["rungs"])},
        {"name": "write_program", "description": "Validate, then replace all rungs of the first POU of an existing .smbp with the rungs (as IL), set timer/counter presets and symbols, and read the file back. A .bak copy is kept.",
         "inputSchema": schema({**LADDER_PROPS, **path}, ["path", "rungs"])},
        {"name": "read_program", "description": "Read a .smbp: POUs with each rung's name, comment and IL, timer/counter presets, symbols and comments.",
         "inputSchema": schema(path, ["path"])},
        {"name": "compile", "description": "Open a .smbp in Machine Expert - Basic, optionally convert every rung to ladder (to_ladder, then the project is saved), run Compile Program and return its status, error count and the IL shown by the editor. Uses the desktop: one call at a time.",
         "inputSchema": schema({**path, "to_ladder": {"type": "boolean", "default": False},
                                "rungs": {"type": "array", "items": RUNG_SCHEMA,
                                          "description": "Optional: compare the editor's IL with these rungs"}}, ["path"])},
    ]


class Server:
    def __init__(self, gui_python: str | None, exe: str | None, allow_write: bool):
        self.gui_python = gui_python
        self.exe = exe
        self.allow_write = allow_write
        self._gui_lock = threading.Lock()

    def _writable(self, path: str) -> Path:
        if not self.allow_write:
            raise PermissionError("writing is disabled; start the server with --allow-write")
        p = Path(path)
        if p.suffix.lower() != ".smbp":
            raise ValueError("path must end with .smbp")
        return p

    def _limits(self, path: str | None):
        return limits_of(parse(read_text(path))) if path else None

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_templates":
            return {"templates": sorted(p.stem for p in TEMPLATES.glob("*.smbp")),
                    "note": "Other controllers: create and save an empty project in Machine Expert - Basic and pass its path."}
        if name == "instructions":
            return {"kinds": KINDS}
        if name == "new_project":
            dest = self._writable(args["path"])
            template = TEMPLATES / f"{args.get('template') or DEFAULT_TEMPLATE}.smbp"
            if not template.exists():
                raise FileNotFoundError(f"unknown template {template.stem!r}")
            if dest.exists():
                raise FileExistsError(f"{dest} exists")
            dest.parent.mkdir(parents=True, exist_ok=True)
            write_project(dest, template, None, {})
            return {"ok": True, "path": str(dest.resolve()), "template": template.stem}
        if name == "read_program":
            return read_project(args["path"])
        rungs, symbols = args.get("rungs", []), args.get("symbols") or {}
        if name == "validate":
            findings = validate(rungs, symbols, self._limits(args.get("path")))
            ok = not findings
            return {"ok": ok, "findings": [f.to_json() for f in findings],
                    "expected_il": expected_il(rungs) if ok else None}
        if name == "write_program":
            path = self._writable(args["path"])
            if not path.exists():
                raise FileNotFoundError(f"{path} does not exist; use new_project first")
            findings = validate(rungs, symbols, self._limits(str(path)))
            if findings:
                return {"ok": False, "written": False, "findings": [f.to_json() for f in findings]}
            backup = str(path) + ".bak"
            shutil.copy2(path, backup)
            tmp = path.with_name(path.name + ".tmp")
            write_project(tmp, path, rungs, symbols, target=path)
            os.replace(tmp, path)
            check = compare(path, rungs)
            if not check["il_matches"]:
                raise FormatError(f"written file does not read back as expected: {check['differences']}")
            return {"ok": True, "written": True, "path": str(path.resolve()), "backup": backup,
                    "rungs": len(rungs), "il": expected_il(rungs), **check}
        if name == "compile":
            return self._compile(args["path"], bool(args.get("to_ladder", False)), args.get("rungs"))
        raise KeyError(f"unknown tool {name!r}")

    def _compile(self, path: str, to_ladder: bool, rungs: list[dict[str, Any]] | None) -> dict[str, Any]:
        if not self.gui_python:
            raise RuntimeError("compile needs --gui-python (Windows Python with pywinauto and pywin32)")
        if to_ladder and not self.allow_write:
            raise PermissionError("to_ladder saves the project; start the server with --allow-write")
        resolved = Path(path).resolve()
        read_text(resolved)  # fail early on a wrong file
        job = {"op": "compile", "path": win_path(str(resolved)), "to_ladder": to_ladder, "save": to_ladder}
        if self.exe:
            job["exe"] = self.exe
        fd, job_path = tempfile.mkstemp(suffix=".json", prefix="schneider_job_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(job, f)
        try:
            with self._gui_lock:
                done = subprocess.run([self.gui_python, win_path(str(GUI_SCRIPT)), win_path(job_path)],
                                      capture_output=True, text=True, timeout=900)
        finally:
            os.unlink(job_path)
        lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
        if not lines:
            return {"ok": False, "error": "GUI driver printed no result", "stderr": done.stderr[-800:]}
        result = json.loads(lines[-1])
        if rungs is not None and "ui_il" in result:
            # the editor shows symbols instead of addresses ("LD START_PB", "LD C_PRODUCTS.D")
            names = {name: addr for addr, name in read_project(resolved)["symbols"].items()}

            def unsymbol(line: str) -> str:
                op, _, operand = normalize_il(line).partition(" ")
                base, dot, member = operand.partition(".")
                return f"{op} {names.get(base, base)}{dot}{member}" if operand else op
            shown = [[unsymbol(line) for line in rung] for rung in result["ui_il"]]
            result["ui_il"] = shown
            result["ui_il_matches"] = shown == expected_il(rungs)
        if to_ladder and result.get("saved"):
            saved = read_project(resolved)["pous"][0]["rungs"]
            result["ladder_rungs"] = sum(1 for r in saved if r["ladder"])
            if rungs is not None:
                result.update(compare(resolved, rungs))
        return result


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
            sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
            sys.stdout.flush()

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
                "serverInfo": {"name": "schneider-mcp", "version": __version__},
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
    parser = argparse.ArgumentParser(prog="schneider-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--allow-write", action="store_true", help="enable new_project, write_program and compile to_ladder")
    parser.add_argument("--gui-python", default=os.environ.get("SCHNEIDER_GUI_PYTHON"),
                        help="Windows python.exe with pywinauto and pywin32, used by compile")
    parser.add_argument("--exe", default=os.environ.get("SCHNEIDER_EXE"),
                        help="SchneiderElectric.SoMachineBasic.MainApplication.exe")
    args = parser.parse_args(argv)
    serve(Server(args.gui_python, args.exe, args.allow_write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
