"""Offline TwinCAT LD engineering through the installed public Automation Interface."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from multiplc.iec_ld import TYPES, expected_logic, parse_logic, to_plcopen, validate
from . import __version__

PROTOCOL_VERSION = "2025-06-18"
SDK = Path(r"C:\Program Files (x86)\Beckhoff\TwinCAT\3.1\Components\Base")
PUBLIC_ASSEMBLIES = Path(r"C:\Program Files\Microsoft Visual Studio\2022\Community\Common7\IDE\PublicAssemblies")
CSC = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")
TLBIMP = Path(r"C:\Program Files (x86)\Microsoft SDKs\Windows\v8.1A\bin\NETFX 4.5.1 Tools\x64\TlbImp.exe")
OWNER = "beckhoff-mcp"
MARKER = ".beckhoff-mcp.json"
FB = {"TON", "TOF", "TP", "CTU"}
INSTRUCTIONS = (
    "Offline TwinCAT RT (x64), not CX7000 or physical I/O validation. Declare named IEC variables; "
    "MAIN is called by PlcTask at 10 ms. Validate rung JSON, then write_ladder to a fresh solution "
    "inside the configured workspace. write_ladder builds, closes/reopens and independently compares "
    "vendor-exported LD, declarations and task binding. build and export_pou reopen in fresh owned "
    "hosts. Existing owned solutions require overwrite=true and are preserved in a sibling .bak directory. "
    "There are no runtime activation, download, online, force or live-value tools."
)


def _schema(properties: dict, required=()) -> dict:
    return {"type": "object", "properties": properties, "required": list(required), "additionalProperties": False}


def tools() -> list[dict]:
    ladder = {
        "variables": {"type": "array", "items": {"type": "object", "properties": {
            "name": {"type": "string"}, "type": {"type": "string", "enum": sorted(TYPES)},
            "address": {"type": "string"}, "comment": {"type": "string"}}, "required": ["name"]}},
        "rungs": {"type": "array", "items": {"type": "object", "properties": {
            "comment": {"type": "string"}, "elements": {"type": "array", "items": {"type": "object"}}}, "required": ["elements"]}},
    }
    path = {"path": {"type": "string", "description": "Solution .sln in a project subdirectory of the configured workspace."}}
    return [
        {"name": "list_targets", "description": "The bounded offline target; this does not claim hardware or runtime support.", "inputSchema": _schema({})},
        {"name": "validate", "description": "Validate MAIN rung JSON and return its expected semantics without filesystem writes.", "inputSchema": _schema(ladder, ["rungs"])},
        {"name": "write_ladder", "description": "Create an owned native solution, author LD, save/reopen, build and verify actual vendor readback. Explicit overwrite preserves the entire prior owned project in a sibling .bak directory.",
         "inputSchema": _schema({**path, **ladder, "overwrite": {"type": "boolean", "default": False}}, ["path", "rungs"])},
        {"name": "build", "description": "Reopen an owned solution in a fresh host and run the real native compiler. Report actual counts separately from failed-project count.", "inputSchema": _schema(path, ["path"])},
        {"name": "export_pou", "description": "Independently export MAIN, declarations and task binding from an owned native solution. No live PLC access.",
         "inputSchema": _schema({**path, "include_xml": {"type": "boolean", "default": False}}, ["path"])},
    ]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def snapshot(xml: str) -> dict:
    root = ET.fromstring(xml.lstrip("\ufeff"))
    matches = [p for p in root.iter() if _local(p.tag) == "pou" and p.get("name") == "MAIN"]
    if len(matches) != 1:
        raise ValueError("Native export must contain exactly one MAIN")
    interface = next((n for n in matches[0] if _local(n.tag) == "interface"), None)
    declarations = {}
    if interface is not None:
        for variable in interface.iter():
            if _local(variable.tag) != "variable" or not variable.get("name"):
                continue
            type_node = next((n for n in variable if _local(n.tag) == "type"), None)
            if type_node is None or len(type_node) != 1:
                raise ValueError("Unsupported native variable type")
            element = type_node[0]
            name = variable.attrib["name"]
            if name in declarations:
                raise ValueError("Duplicate native declaration")
            declarations[name] = {"type": element.get("name") if _local(element.tag) == "derived" else _local(element.tag),
                                  "address": variable.get("address", "")}
    tasks = []
    for task in root.iter():
        if _local(task.tag) != "task":
            continue
        calls = [n.get("name") for n in task if _local(n.tag) == "pouInstance"]
        settings = next((n for n in task.iter() if _local(n.tag) == "TaskSettings"), None)
        tasks.append({"name": task.get("name"), "calls": calls, "settings": dict(settings.attrib) if settings is not None else {}})
    return {"logic": parse_logic(xml, "MAIN"), "declarations": declarations, "tasks": tasks}


def verify_readback(xml: str, variables: list[dict], rungs: list[dict]) -> dict:
    actual = snapshot(xml)
    wanted = {v["name"]: {"type": v.get("type", "BOOL"), "address": v.get("address", "")} for v in variables}
    for rung in rungs:
        output = rung["elements"][-1]
        if output["kind"] in FB:
            wanted[output["args"][0]] = {"type": output["kind"], "address": ""}
    bound = any(t["name"] == "PlcTask" and "MAIN" in t["calls"] and t["settings"].get("KindOfTask") == "Cyclic"
                and t["settings"].get("Interval") == "10000" and t["settings"].get("IntervalUnit") == "us" for t in actual["tasks"])
    return {**actual, "logic_matches": actual["logic"] == expected_logic(rungs),
            "declarations_match": actual["declarations"] == wanted, "task_bound": bound}


class Server:
    def __init__(self, workspace: Path, allow_write: bool = False, *, sdk: Path = SDK,
                 public_assemblies: Path = PUBLIC_ASSEMBLIES, compiler: Path = CSC, tlbimp: Path = TLBIMP):
        self.workspace = Path(workspace).resolve()
        self.allow_write = allow_write
        self.sdk, self.assemblies, self.compiler, self.tlbimp = map(Path, (sdk, public_assemblies, compiler, tlbimp))
        self._runtime: tempfile.TemporaryDirectory | None = None
        self._lock = threading.Lock()

    def close(self) -> None:
        if self._runtime is not None:
            self._runtime.cleanup()
            self._runtime = None

    def _path(self, value: str) -> Path:
        path = Path(value).expanduser()
        path = (self.workspace / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_relative_to(self.workspace) or path.parent == self.workspace or path.suffix.lower() != ".sln":
            raise PermissionError("path must be a .sln in a project subdirectory of the configured workspace")
        return path

    def _owned(self, path: Path) -> None:
        marker = path.parent / MARKER
        if not path.is_file() or not marker.is_file():
            raise FileExistsError("Only solutions created by this backend can be opened or overwritten")
        data = json.loads(marker.read_text(encoding="utf-8"))
        if data.get("owner") != OWNER or data.get("solution") != path.name:
            raise PermissionError("Project ownership marker does not match this solution")

    def _prepare(self) -> Path:
        if self._runtime is not None:
            return Path(self._runtime.name) / "NativeJob.exe"
        if os.name != "nt":
            raise OSError("Native TwinCAT engineering requires Windows; validation remains available here")
        tlb = self.sdk / "TypeLib" / "3.4" / "TCatSysManager.tlb"
        references = [self.assemblies / name for name in ("envdte.dll", "envdte80.dll", "Microsoft.VisualStudio.Interop.dll")]
        for dependency in [self.compiler, self.tlbimp, tlb, *references, self.sdk / "PrjTemplate" / "TwinCAT Project.tsproj"]:
            if not dependency.is_file():
                raise FileNotFoundError(f"Required installed public SDK component missing: {dependency}. No automatic installation is attempted.")
        runtime = tempfile.TemporaryDirectory(prefix="beckhoff_mcp_runtime_")
        try:
            folder = Path(runtime.name)
            interop, helper = folder / "TCatSysManagerLib.dll", folder / "NativeJob.exe"
            commands = [
                [str(self.tlbimp), str(tlb), f"/out:{interop}", "/namespace:TCatSysManagerLib", "/machine:Agnostic", "/nologo"],
                [str(self.compiler), "/nologo", "/target:exe", "/platform:x64", f"/out:{helper}", f"/reference:{interop}",
                 *[f"/reference:{p}" for p in references], "/reference:System.Web.Extensions.dll", str(Path(__file__).with_name("NativeJob.cs"))],
            ]
            for command in commands:
                completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
                if completed.returncode:
                    raise RuntimeError("Public SDK worker compilation failed: " + (completed.stdout + completed.stderr)[-4000:])
            self._runtime = runtime
            return helper
        except BaseException:
            runtime.cleanup()
            raise

    def _run(self, operation: str, path: Path, xml: str | None = None) -> dict:
        helper = self._prepare()
        with tempfile.TemporaryDirectory(prefix="beckhoff_mcp_job_") as folder:
            work = Path(folder)
            job = {"op": operation, "solution": str(path), "public_assemblies": str(self.assemblies),
                   "template": str(self.sdk / "PrjTemplate" / "TwinCAT Project.tsproj"),
                   "result_path": str(work / "result.json"), "export_path": str(work / "vendor-export.xml")}
            if xml is not None:
                (work / "input.xml").write_text(xml, encoding="utf-8")
                job["xml_path"] = str(work / "input.xml")
            (work / "job.json").write_text(json.dumps(job), encoding="utf-8")
            completed = subprocess.run([str(helper), str(work / "job.json")], capture_output=True, text=True, encoding="utf-8-sig", timeout=240)
            result_file = work / "result.json"
            if not result_file.is_file():
                raise RuntimeError(f"Native worker returned no receipt (exit {completed.returncode}): {(completed.stderr or '')[-2000:]}")
            return json.loads(result_file.read_text(encoding="utf-8-sig"))

    def call(self, name: str, args: dict[str, Any]) -> Any:
        definitions = {t["name"]: t["inputSchema"] for t in tools()}
        if name not in definitions:
            raise KeyError(f"Unknown tool {name!r}")
        if name == "write_ladder" and not self.allow_write:
            raise PermissionError("writing is disabled; start the server with --allow-write")
        schema = definitions[name]
        if not isinstance(args, dict) or set(args) - set(schema["properties"]) or set(schema["required"]) - set(args):
            raise ValueError("Missing or unsupported tool arguments")
        if name == "list_targets":
            return {"targets": [{"platform": "TwinCAT RT (x64)", "pou": "MAIN", "task": "PlcTask", "cycle_us": 10000,
                                 "scope": "offline engineering; logical I/O only", "cx7000_verified": False, "simulation_verified": False, "hardware_verified": False}]}
        variables, rungs = args.get("variables") or [], args.get("rungs") or []
        if name in ("validate", "write_ladder"):
            findings = validate("MAIN", variables, rungs)
            if findings:
                return {"ok": False, "written": False, "findings": [f.to_json() for f in findings]}
            xml = to_plcopen("MAIN", variables, rungs)
            if name == "validate":
                return {"ok": True, "expected_logic": expected_logic(rungs), "plcopen_xml": xml}
        path = self._path(args["path"])
        with self._lock:
            backup = None
            if name == "write_ladder":
                if not isinstance(args.get("overwrite", False), bool):
                    raise ValueError("overwrite must be a boolean")
                if path.parent.exists() and any(path.parent.iterdir()):
                    self._owned(path)
                    if not args.get("overwrite", False):
                        raise FileExistsError("Solution exists; pass overwrite=true to preserve it in a sibling .bak directory")
                    backup_path = path.parent.with_name(path.parent.name + ".bak")
                    if backup_path.exists():
                        raise FileExistsError("Backup directory already exists; it will not be overwritten")
                    # Verify the native toolchain before moving any existing project.
                    self._prepare()
                    path.parent.rename(backup_path)
                    backup = str(backup_path)
                else:
                    self._prepare()
                path.parent.mkdir(parents=True, exist_ok=True)
                (path.parent / MARKER).write_text(json.dumps({"owner": OWNER, "solution": path.name}), encoding="utf-8")
                result = self._run("write", path, xml)
                result["backup"] = backup
                exported = result.pop("export_xml", None)
                if exported:
                    verification = verify_readback(exported, variables, rungs)
                    result.update(verification)
                    result["ok"] = bool(result.get("ok") and all(verification[k] for k in ("logic_matches", "declarations_match", "task_bound")))
                else:
                    result["ok"] = False
                    result["readback_error"] = "Native worker produced no independent export"
                result["written"] = path.is_file()
                result["simulation_verified"] = result["hardware_verified"] = False
                if exported:
                    result["native_export_sha256"] = hashlib.sha256(exported.encode("utf-8")).hexdigest()
                return result
            self._owned(path)
            result = self._run("build" if name == "build" else "export", path)
            exported = result.pop("export_xml", None)
            if exported:
                result.update(snapshot(exported))
                result["native_export_sha256"] = hashlib.sha256(exported.encode("utf-8")).hexdigest()
                if args.get("include_xml"):
                    result["plcopen_xml"] = exported
            elif result.get("ok"):
                result["ok"] = False
                result["readback_error"] = "Native worker produced no independent export"
            return result


def serve(server: Server) -> None:
    def send(message: dict) -> None:
        sys.stdout.buffer.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        sys.stdout.buffer.flush()
    for line in sys.stdin.buffer:
        try:
            message = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
            continue
        if not isinstance(message, dict):
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}})
            continue
        if "id" not in message:
            continue
        rid, method, params = message["id"], message.get("method"), message.get("params") or {}
        reply = {"jsonrpc": "2.0", "id": rid}
        if method == "initialize":
            reply["result"] = {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {"listChanged": False}},
                               "serverInfo": {"name": OWNER, "version": __version__}, "instructions": INSTRUCTIONS}
        elif method == "ping":
            reply["result"] = {}
        elif method == "tools/list":
            reply["result"] = {"tools": tools()}
        elif method == "tools/call":
            try:
                payload = server.call(params.get("name"), params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]}
                if isinstance(payload, dict) and payload.get("ok") is False:
                    result["isError"] = True
                reply["result"] = result
            except Exception as error:
                reply["result"] = {"isError": True, "content": [{"type": "text", "text": json.dumps({"error": f"{type(error).__name__}: {error}"})}]}
        else:
            reply["error"] = {"code": -32601, "message": f"method not found: {method}"}
        send(reply)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--workspace", type=Path, default=Path.home() / ".multi-plc-agent" / "beckhoff")
    parser.add_argument("--sdk", type=Path, default=SDK)
    parser.add_argument("--public-assemblies", type=Path, default=PUBLIC_ASSEMBLIES)
    parser.add_argument("--compiler", type=Path, default=CSC)
    parser.add_argument("--tlbimp", type=Path, default=TLBIMP)
    args = parser.parse_args(argv)
    server = Server(args.workspace, args.allow_write, sdk=args.sdk, public_assemblies=args.public_assemblies,
                    compiler=args.compiler, tlbimp=args.tlbimp)
    try:
        serve(server)
    finally:
        server.close()
    return 0
