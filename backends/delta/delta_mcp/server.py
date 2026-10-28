"""MCP stdio server for Delta WPLSoft 2.52 (DVP-ES2/SS2 series).

write_ladder turns rung JSON into DVP instruction list, encodes it into the
.dvp program area directly (the area is a word stream XOR-ed with a per-file
key byte, see dvp.py), then opens the project in its own WPLSoft process to
run the grammar check (Compiler > Instruction => Ladder and Ladder =>
Instruction) and save it through WPLSoft. read_il decodes the program back
from the file. Everything runs offline; nothing is sent to a PLC.
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
from .dvp import device_comments, patch, read_il, segment_comments
from .il import expected_il, il_text, device_notes, validate

PROTOCOL_VERSION = "2025-06-18"
GUI_SCRIPT = Path(__file__).with_name("wplsoft_gui.py")
TEMPLATES = Path(__file__).with_name("templates")

RUNG_SCHEMA = {
    "type": "object",
    "properties": {"comment": {"type": "string"}, "elements": {"type": "array", "items": {"type": "object"}}},
    "required": ["elements"],
}
LADDER_PROPS = {
    "rungs": {"type": "array", "items": RUNG_SCHEMA},
    "aliases": {"type": "object", "additionalProperties": {"type": "string"},
                "description": "Device comment per address, e.g. {\"X0\": \"Start PB\"}"},
}

INSTRUCTIONS = (
    "Delta DVP-ES2/SS2 addresses: inputs X0.. and outputs Y0.. (octal: X7 then X10), relays M0..M4095, "
    "steps S0..S1023, timers T0..T255 (T0..T199 count in 100 ms: K30 = 3 s), 16-bit counters C0..C199. "
    "Rung elements: contacts {kind: NO|NC, args: [addr], note?}, parallel {branch: [[...], [...]]} (legs are "
    "series of contacts/branches, nesting allowed), then exactly one output: OUT [Y|M|S], SET [Y|M|S], "
    "RST [addr], TMR [Tn, Kpreset], CNT [Cn, Kpreset]. Notes and aliases become device comments. Rung "
    "comments are not written (WPLSoft segment comments need a binary record this backend does not "
    "produce). Call delta_validate, then delta_write_ladder (replaces the whole program of a .dvp, checks "
    "it in WPLSoft and saves), then delta_read_il to verify."
)


def _tools() -> list[dict[str, Any]]:
    def schema(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
    return [
        {"name": "list_templates", "description": "Empty project templates (PLC models) new_project can copy.",
         "inputSchema": schema({})},
        {"name": "new_project", "description": "Create an empty .dvp from a template (saved from WPLSoft 2.52). Refuses to overwrite.",
         "inputSchema": schema({"path": {"type": "string"}, "template": {"type": "string"}}, ["path"])},
        {"name": "validate", "description": "Check rungs (structure, ES2/SS2 device ranges, presets) and return the IL they compile to. Writes nothing.",
         "inputSchema": schema(LADDER_PROPS, ["rungs"])},
        {"name": "write_ladder", "description": "Replace the whole program of a .dvp with the rungs, add device comments, run WPLSoft's grammar check (Instruction => Ladder, Ladder => Instruction) and save through WPLSoft. Keeps a .bak copy; the file is restored if the check fails.",
         "inputSchema": schema({**LADDER_PROPS, "path": {"type": "string"}}, ["path", "rungs"])},
        {"name": "compile", "description": "Open a .dvp in WPLSoft and run Compiler > Instruction => Ladder and Ladder => Instruction. Returns error count and messages. Does not save.",
         "inputSchema": schema({"path": {"type": "string"}}, ["path"])},
        {"name": "read_il", "description": "Decode the program of a .dvp into instruction list, with device and segment comments. Needs no WPLSoft.",
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
        fd, job_path = tempfile.mkstemp(suffix=".json", prefix="delta_job_")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(job, f)
        try:
            with self._gui_lock:
                done = subprocess.run([self.gui_python, str(GUI_SCRIPT), _win_path(job_path)],
                                      capture_output=True, text=True, timeout=300)
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
        if p.suffix.lower() != ".dvp":
            raise ValueError("path must end with .dvp")
        return p

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_templates":
            return {"templates": sorted(p.stem for p in TEMPLATES.glob("*.dvp")),
                    "note": "SS2 also fits ES2 programs of this size. Other models: create the project in WPLSoft (File > New) and pass its path."}
        if name == "new_project":
            dest = self._writable(args["path"])
            template = TEMPLATES / f"{args.get('template') or 'SS2'}.dvp"
            if not template.exists():
                raise FileNotFoundError(f"unknown template {template.stem!r}")
            if dest.exists():
                raise FileExistsError(f"{dest} exists")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(template, dest)
            return {"ok": True, "path": str(dest.resolve()), "template": template.stem}
        if name == "read_il":
            data = Path(args["path"]).read_bytes()
            notes = {a: t for a, t in device_comments(data).items() if not _builtin_comment(a)}
            return {"il": il_text(read_il(data)), "device_comments": notes,
                    "segment_comments": [{"row": r, "text": t} for r, t in segment_comments(data)]}
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
            want = expected_il(rungs)
            template = TEMPLATES / "SS2.dvp"
            original = path.read_bytes()
            # Start from an empty project with the same header so WPLSoft draws the
            # ladder from the new program (a filled project keeps its old layout).
            base = original if not read_il(original) else _same_model_template(original, template)
            backup = Path(str(path) + ".bak")
            shutil.copy2(path, backup)
            path.write_bytes(patch(base, want, device_notes(rungs, aliases)))
            result = self._gui({"op": "compile", "path": _win_path(str(path.resolve())), "save": True})
            got = read_il(path.read_bytes())
            result["il"] = il_text(got)
            result["il_matches"] = got == want
            if not result.get("ok") or got != want:
                result["ok"] = False
                result["expected_il"] = il_text(want)
                shutil.copy2(backup, path)
                result["restored_backup"] = True
            result.update({"written": result["ok"], "backup": str(backup), "rungs": len(rungs),
                           "rung_comments_written": False})
            return result
        if name == "compile":
            return self._gui({"op": "compile", "path": _win_path(str(Path(args["path"]).resolve())), "save": False})
        raise KeyError(f"unknown tool {name!r}")


def _builtin_comment(addr: str) -> bool:
    """WPLSoft ships preset comments for special relays M1000.. and registers D1000.."""
    kind, number = addr[:1], addr[1:]
    return kind not in "XYMSTC" or (kind == "M" and number.isdigit() and int(number) >= 1000)


def _same_model_template(original: bytes, template: Path) -> bytes:
    """Empty template for a project that already holds a program (same model only)."""
    data = template.read_bytes()
    if original[0x4A:0x56] != data[0x4A:0x56]:
        raise ValueError("this project already has a program and is not an SS2 project; "
                         "create an empty project for its model in WPLSoft and write into that")
    return data


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
                "serverInfo": {"name": "delta-mcp", "version": __version__},
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
    parser = argparse.ArgumentParser(prog="delta-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--allow-write", action="store_true", help="enable new_project and write_ladder")
    parser.add_argument("--gui-python", default=os.environ.get("DELTA_GUI_PYTHON"),
                        help="Windows python.exe with pywinauto and pywin32")
    parser.add_argument("--wplsoft-exe", default=os.environ.get("WPLSOFT_EXE"))
    args = parser.parse_args(argv)
    serve(Server(args.gui_python, args.wplsoft_exe, args.allow_write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
