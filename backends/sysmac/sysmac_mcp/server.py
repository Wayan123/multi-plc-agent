"""MCP stdio server for Omron Sysmac Studio 1.47 (NJ/NX ladder through IEC 61131-10 XML).

write_program turns rung JSON into an IEC 61131-10 XML LD program, imports it into the open
Sysmac Studio project (Tools > IEC 61131-10 XML > Import; a new NX1P2 project is created when
none is open), runs Check All Programs + Build Controller, saves, and compares the ladder
listing Sysmac stored with the logic implied by the rung JSON. Nothing is transferred to a
Controller.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

from . import __version__
from .ladder import OUTPUTS, TYPES, expected_logic, parse_listing, to_iec_xml, validate

PROTOCOL_VERSION = "2025-06-18"
GUI_SCRIPT = Path(__file__).with_name("sysmac_gui.py")
DEVICES = ["NX1P2-1040DT", "NX1P2-1140DT", "NX1P2-9024DT", "NX102-9000", "NJ501-1500", "NJ101-1000"]

VAR_SCHEMA = {"type": "object", "properties": {
    "name": {"type": "string"}, "type": {"type": "string", "enum": list(TYPES)}, "comment": {"type": "string"}},
    "required": ["name"]}
RUNG_SCHEMA = {"type": "object", "properties": {
    "comment": {"type": "string"}, "elements": {"type": "array", "items": {"type": "object"}}}, "required": ["elements"]}
LADDER_PROPS = {
    "program": {"type": "string", "default": "AgentProgram", "description": "Program POU name"},
    "variables": {"type": "array", "items": VAR_SCHEMA},
    "rungs": {"type": "array", "items": RUNG_SCHEMA},
}

INSTRUCTIONS = (
    "Sysmac Studio ladder uses named variables. Declare every BOOL in variables (program-local). Rung elements: "
    "contacts {kind: NO|NC, args: [name]}, parallel {branch: [[...],[...]]} (nesting allowed), then one output: "
    "OUT/SET/RST [bool], TON/TOF/TP [instance, T#3s], CTU [instance, PV, reset_bool]. Instances are declared "
    "automatically; contacts read them as <instance>.Q. Call sysmac_validate, then sysmac_write_program (imports "
    "into the open project or a new NX1P2 project, builds, saves and compares the stored ladder), sysmac_build to "
    "re-check, sysmac_read_program for read-back. Map variables to I/O ports in Sysmac Studio's I/O Map yourself; "
    "nothing is transferred to a Controller. Uses the desktop: one call at a time."
)


def _tools() -> list[dict[str, Any]]:
    def schema(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
    return [
        {"name": "list_devices", "description": "Controller models write_program can create a new project for.",
         "inputSchema": schema({})},
        {"name": "validate", "description": "Check variables and rungs and return the IEC 61131-10 XML and expected logic. Writes nothing.",
         "inputSchema": schema(LADDER_PROPS, ["rungs"])},
        {"name": "write_program", "description": "Import the LD program into Sysmac Studio (replacing a program with the same name), build, save and verify the stored ladder against the rung JSON. Creates a new project for 'device' if none is open.",
         "inputSchema": schema({**LADDER_PROPS, "device": {"type": "string", "enum": DEVICES, "default": "NX1P2-1040DT"},
                                "project_name": {"type": "string"},
                                "xml_path": {"type": "string", "description": "optional: keep the generated XML here"}}, ["rungs"])},
        {"name": "build", "description": "Run Check All Programs and Build Controller in the open project. Returns error/warning counts and Build tab messages.",
         "inputSchema": schema({})},
        {"name": "read_program", "description": "Save the open project and return the stored ladder of one program as logic per rung (output, target, canonical boolean expression, parameters).",
         "inputSchema": schema({"program": {"type": "string"}, "include_listing": {"type": "boolean", "default": False}}, ["program"])},
    ]


class Server:
    def __init__(self, gui_python: str | None, sysmac_exe: str | None, allow_write: bool):
        self.gui_python = gui_python
        self.sysmac_exe = sysmac_exe
        self.allow_write = allow_write
        self._lock = threading.Lock()

    def _gui(self, job: dict[str, Any], timeout: int = 900) -> dict[str, Any]:
        if not self.gui_python:
            raise RuntimeError("this tool needs --gui-python (Windows Python with pywinauto + pywin32)")
        if self.sysmac_exe:
            job = {**job, "exe": self.sysmac_exe}
        fd, job_path = tempfile.mkstemp(suffix=".json", prefix="sysmac_job_", dir=str(GUI_SCRIPT.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(job, f)
        try:
            with self._lock:
                done = subprocess.run([self.gui_python, _win(str(GUI_SCRIPT)), _win(job_path)],
                                      capture_output=True, text=True, timeout=timeout)
        finally:
            os.unlink(job_path)
        lines = [line for line in done.stdout.splitlines() if line.startswith("{")]
        if not lines:
            return {"ok": False, "error": "GUI driver printed no result", "stderr": done.stderr[-800:]}
        return json.loads(lines[-1])

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_devices":
            return {"devices": DEVICES}
        program = args.get("program") or "AgentProgram"
        variables, rungs = args.get("variables") or [], args.get("rungs") or []
        if name == "validate":
            findings = validate(program, variables, rungs)
            ok = not findings
            return {"ok": ok, "findings": [f.to_json() for f in findings],
                    "expected_logic": expected_logic(rungs) if ok else None,
                    "iec_xml": to_iec_xml(program, variables, rungs) if ok else None}
        if name == "write_program":
            if not self.allow_write:
                raise PermissionError("writing is disabled; start the server with --allow-write")
            findings = validate(program, variables, rungs)
            if findings:
                return {"ok": False, "written": False, "findings": [f.to_json() for f in findings]}
            device = args.get("device") or "NX1P2-1040DT"
            xml = to_iec_xml(program, variables, rungs, model=device)
            if args.get("xml_path"):
                xml_path, keep = Path(args["xml_path"]), True
            else:
                fd, tmp = tempfile.mkstemp(suffix=".xml", prefix="sysmac_pou_")
                os.close(fd)
                xml_path, keep = Path(tmp), False
            xml_path.write_text(xml, encoding="utf-8")
            try:
                result = self._gui({"op": "import", "xml": _win(str(xml_path)), "program": program, "device": device,
                                    "project_name": args.get("project_name") or program})
            finally:
                if not keep:
                    xml_path.unlink(missing_ok=True)
            return _verify(result, program, rungs)
        if name == "build":
            return self._gui({"op": "build"})
        if name == "read_program":
            result = self._gui({"op": "read", "program": args["program"]})
            if result.get("sections"):
                result["logic"] = [r for s in result["sections"] for r in parse_listing(s["listing"])]
                if not args.get("include_listing"):
                    result["sections"] = [s["name"] for s in result["sections"]]
            return result
        raise KeyError(f"unknown tool {name!r}")


def _verify(result: dict[str, Any], program: str, rungs: list[dict[str, Any]]) -> dict[str, Any]:
    sections = result.pop("sections", None)
    result.pop("variables_text", None)
    result["rungs"] = len(rungs)
    if not result.get("imported"):
        result["ok"] = False
        return result
    if not sections:
        result["ok"] = False
        result["error"] = f"program {program!r} was imported but its stored ladder was not found"
        return result
    got = [r for s in sections for r in parse_listing(s["listing"])]
    want = expected_logic(rungs)
    result["logic_matches"] = got == want
    if got != want:
        result["ok"] = False
        result["logic"], result["expected_logic"] = got, want
    return result


def _win(path: str) -> str:
    """WSL path -> Windows path for the Windows-side GUI driver; Windows paths pass through."""
    if path.startswith("/mnt/") and len(path) > 6 and path[6] == "/":
        return f"{path[5].upper()}:\\" + path[7:].replace("/", "\\")
    if path.startswith("/"):
        try:
            return subprocess.run(["wslpath", "-w", path], capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return path
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
                "serverInfo": {"name": "sysmac-mcp", "version": __version__},
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
    parser = argparse.ArgumentParser(prog="sysmac-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--allow-write", action="store_true", help="enable write_program")
    parser.add_argument("--gui-python", default=os.environ.get("SYSMAC_GUI_PYTHON"),
                        help="Windows python.exe with pywinauto + pywin32")
    parser.add_argument("--sysmac-exe", default=os.environ.get("SYSMAC_EXE"))
    args = parser.parse_args(argv)
    serve(Server(args.gui_python, args.sysmac_exe, args.allow_write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
