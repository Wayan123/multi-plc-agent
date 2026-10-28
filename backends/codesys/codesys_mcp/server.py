"""MCP stdio server for the CODESYS Development System V3.5 (headless ScriptEngine).

write_ladder turns rung JSON into a PLCopen XML LD program, starts CODESYS with
--noUI --runscript, creates a project for the chosen device (default CODESYS
Control Win V3 x64), imports the program, builds it and exports it back. The
exported logic is compared with the logic implied by the rung JSON. Nothing is
downloaded to a PLC.
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
from .ladder import OUTPUTS, TYPES, expected_logic, parse_logic, to_plcopen, validate

PROTOCOL_VERSION = "2025-06-18"
JOB_SCRIPT = Path(__file__).with_name("codesys_job.py")
DEFAULT_EXE = r"C:\Program Files\CODESYS 3.5.21.0\CODESYS\Common\CODESYS.exe"
DEFAULT_PROFILE = "CODESYS V3.5 SP21"
# Device identities from the local device repository (type, id, version)
DEVICES = {
    "control_win_x64": {"type": 4096, "id": "0000 0004", "version": "3.5.21.0", "name": "CODESYS Control Win V3 x64"},
    "control_win": {"type": 4096, "id": "0000 0001", "version": "3.5.21.0", "name": "CODESYS Control Win V3"},
}

VAR_SCHEMA = {"type": "object", "properties": {
    "name": {"type": "string"}, "type": {"type": "string", "enum": list(TYPES)},
    "address": {"type": "string", "description": "optional direct address, e.g. %IX0.0, %QX0.1"},
    "comment": {"type": "string"}}, "required": ["name"]}
RUNG_SCHEMA = {"type": "object", "properties": {
    "comment": {"type": "string"}, "elements": {"type": "array", "items": {"type": "object"}}}, "required": ["elements"]}
LADDER_PROPS = {
    "pou": {"type": "string", "default": "PLC_PRG"},
    "variables": {"type": "array", "items": VAR_SCHEMA},
    "rungs": {"type": "array", "items": RUNG_SCHEMA},
}

INSTRUCTIONS = (
    "CODESYS LD uses named IEC variables. Declare every BOOL in variables (optionally with an address such as "
    "%IX0.0 or %QX0.0). Rung elements: contacts {kind: NO|NC, args: [name]}, parallel {branch: [[...],[...]]} "
    "(nesting allowed), then one output: OUT/SET/RST [bool], TON/TOF/TP [instance, T#3S], CTU [instance, PV, "
    "reset_bool]. Instances are declared automatically; contacts read them as <instance>.Q. Call codesys_validate, "
    "then codesys_write_ladder (new .project, build, export back and compare), then codesys_build for a re-check. "
    "Nothing is downloaded to a PLC."
)


def _tools() -> list[dict[str, Any]]:
    def schema(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}
    return [
        {"name": "list_devices", "description": "Devices write_ladder can create a project for.", "inputSchema": schema({})},
        {"name": "validate", "description": "Check variables and rungs (identifiers, types, addresses, outputs) and return the PLCopen XML and expected logic. Writes nothing.",
         "inputSchema": schema(LADDER_PROPS, ["rungs"])},
        {"name": "write_ladder", "description": "Create a CODESYS .project with the LD program, build it headless and verify the exported logic. An existing file is kept as <file>.bak only when overwrite=true.",
         "inputSchema": schema({**LADDER_PROPS, "path": {"type": "string"}, "device": {"type": "string", "enum": sorted(DEVICES), "default": "control_win_x64"},
                                "overwrite": {"type": "boolean", "default": False}}, ["path", "rungs"])},
        {"name": "build", "description": "Open a CODESYS .project headless and build its Application. Returns error/warning counts and messages.",
         "inputSchema": schema({"path": {"type": "string"}}, ["path"])},
        {"name": "export_pou", "description": "Read one POU of a .project back: its logic per network (output, target, canonical boolean expression, parameters). include_xml adds the PLCopen XML.",
         "inputSchema": schema({"path": {"type": "string"}, "pou": {"type": "string", "default": "PLC_PRG"},
                                "include_xml": {"type": "boolean", "default": False}}, ["path"])},
    ]


class Server:
    def __init__(self, exe: str, profile: str, allow_write: bool):
        self.exe = exe
        self.profile = profile
        self.allow_write = allow_write
        self._lock = threading.Lock()

    def _run(self, job: dict[str, Any], timeout: int = 600) -> dict[str, Any]:
        if not Path(self.exe).exists():
            raise FileNotFoundError(f"CODESYS not found at {self.exe}; pass --codesys-exe")
        workdir = Path(tempfile.mkdtemp(prefix="codesys_mcp_"))
        try:
            job_path = workdir / "job.json"
            job_path.write_text(json.dumps(job), encoding="utf-8")
            env = {**os.environ, "CODESYS_MCP_JOB": str(job_path)}
            with self._lock:
                # CODESYS parses --profile="..." itself; pass one pre-quoted command line
                cmd = f'"{self.exe}" --profile="{self.profile}" --noUI --runscript="{JOB_SCRIPT}"'
                done = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
            result_path = Path(str(job_path) + ".result.json")
            if not result_path.exists():
                return {"ok": False, "error": "CODESYS wrote no result", "exit_code": done.returncode,
                        "stderr": (done.stderr or "")[-800:]}
            return json.loads(result_path.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    def call(self, name: str, args: dict[str, Any]) -> Any:
        if name == "list_devices":
            return {"devices": [{"key": k, **v} for k, v in DEVICES.items()]}
        pou = args.get("pou") or "PLC_PRG"
        variables, rungs = args.get("variables") or [], args.get("rungs") or []
        if name == "validate":
            findings = validate(pou, variables, rungs)
            ok = not findings
            return {"ok": ok, "findings": [f.to_json() for f in findings],
                    "expected_logic": expected_logic(rungs) if ok else None,
                    "plcopen_xml": to_plcopen(pou, variables, rungs) if ok else None}
        if name == "write_ladder":
            if not self.allow_write:
                raise PermissionError("writing is disabled; start the server with --allow-write")
            path = Path(args["path"])
            if path.suffix.lower() != ".project":
                raise ValueError("path must end with .project")
            findings = validate(pou, variables, rungs)
            if findings:
                return {"ok": False, "written": False, "findings": [f.to_json() for f in findings]}
            backup = None
            if path.exists():
                if not args.get("overwrite", False):
                    raise FileExistsError(f"{path} exists; pass overwrite=true to replace it (a .bak copy is kept)")
                backup = str(path) + ".bak"
                shutil.copy2(path, backup)
            path.parent.mkdir(parents=True, exist_ok=True)
            device = DEVICES[args.get("device") or "control_win_x64"]
            xml_fd, xml_path = tempfile.mkstemp(suffix=".xml", prefix="codesys_pou_")
            with os.fdopen(xml_fd, "w", encoding="utf-8") as f:
                f.write(to_plcopen(pou, variables, rungs))
            try:
                result = self._run({"op": "write", "project": str(path.resolve()), "pou": pou,
                                    "device": device, "xml_path": xml_path})
            finally:
                os.unlink(xml_path)
            result["backup"] = backup
            exported = result.pop("export_xml", None)
            if exported:
                got, want = parse_logic(exported, pou), expected_logic(rungs)
                result["logic_matches"] = got == want
                if got != want:
                    result["ok"] = False
                    result["logic"], result["expected_logic"] = got, want
            elif result.get("ok"):
                result["ok"] = False
                result["error"] = "build passed but the POU could not be exported for verification"
            result["rungs"] = len(rungs)
            return result
        if name == "build":
            return self._run({"op": "build", "project": str(Path(args["path"]).resolve())})
        if name == "export_pou":
            result = self._run({"op": "export", "project": str(Path(args["path"]).resolve()), "pou": pou})
            xml = (result.pop("export_xml", None) or "").lstrip("\ufeff")
            if xml:
                result["logic"] = parse_logic(xml, pou)
                if args.get("include_xml"):
                    result["plcopen_xml"] = xml
            return result
        raise KeyError(f"unknown tool {name!r}")


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
                "serverInfo": {"name": "codesys-mcp", "version": __version__},
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
    parser = argparse.ArgumentParser(prog="codesys-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--allow-write", action="store_true", help="enable write_ladder")
    parser.add_argument("--codesys-exe", default=os.environ.get("CODESYS_EXE", DEFAULT_EXE))
    parser.add_argument("--profile", default=os.environ.get("CODESYS_PROFILE", DEFAULT_PROFILE))
    args = parser.parse_args(argv)
    serve(Server(args.codesys_exe, args.profile, args.allow_write))
    return 0


if __name__ == "__main__":
    sys.exit(main())
