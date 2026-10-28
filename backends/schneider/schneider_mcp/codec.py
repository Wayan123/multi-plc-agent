"""Rung model, IL generation and .smbp read/write for Machine Expert - Basic (M221).

A Machine Expert - Basic project (.smbp) is a UTF-8 (BOM) XmlSerializer document
without checksums. Each rung is a <RungEntity> holding its IL
(<InstructionLines>) and, when shown as ladder, the ladder grid
(<LadderElements>). Rungs written here carry IL only with
IsLadderSelected=false; Machine Expert - Basic compiles them as they are and can
turn them into ladder itself (the rung's LD/IL selector). Symbols and comments
live in the object tables (DiscretInput, DiscretOutput, MemoryBit, TimerTM,
Counter).

Rung JSON:
    {"comment": "Run request", "elements": [
        {"branch": [[{"kind": "NO", "args": ["%I0.0"], "note": "Start"}],
                    [{"kind": "NO", "args": ["%M0"]}]]},
        {"kind": "NC", "args": ["%I0.1"], "note": "Stop"},
        {"kind": "OUT", "args": ["%M0"], "note": "Run"}]}
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

XSI = "http://www.w3.org/2001/XMLSchema-instance"
ET.register_namespace("xsi", XSI)
ET.register_namespace("xsd", "http://www.w3.org/2001/XMLSchema")

TEMPLATES = Path(__file__).with_name("templates")
DEFAULT_TEMPLATE = "TM221M16R"

# contact kind -> IL modifier (LD/AND/OR + modifier)
CONTACTS = {"NO": "", "NC": "N", "RE": "R", "FE": "F"}
# bit output kind -> IL instruction
COILS = {"OUT": "ST", "OUTN": "STN", "SET": "S", "RST": "R"}
TIMERS = {"TON": None, "TOF": "TOF", "TP": "TP"}  # None = default type, no <Type> element
BLOCKS = (*TIMERS, "CTU")
TIME_BASES = {"1ms": "OneMilliSeconds", "10ms": "TenMilliSeconds", "100ms": "OneHundredMilliSeconds",
              "1s": "OneSecond", "1min": "OneMinute"}
KINDS = {**{k: "contact: [bit]" for k in CONTACTS}, **{k: "output: [bit]" for k in COILS},
         **{k: "timer block: [%TMn, preset, time base 1ms|10ms|100ms|1s|1min (default 1s)]" for k in TIMERS},
         "CTU": "up-counter block: [%Cn, preset, optional reset input bit]"}

INPUT = re.compile(r"^%I0\.(\d+)$")
OUTPUT = re.compile(r"^%Q0\.(\d+)$")
MEMORY = re.compile(r"^%M(\d+)$")
SYSTEM = re.compile(r"^%S(\d+)$")
TIMER = re.compile(r"^%TM(\d+)$")
COUNTER = re.compile(r"^%C(\d+)$")
TIMER_BIT = re.compile(r"^%TM(\d+)\.Q$")
COUNTER_BIT = re.compile(r"^%C(\d+)\.(D|E|F)$")
SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")


class FormatError(ValueError):
    pass


@dataclass
class Finding:
    rung: int | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"level": "error", "rung": self.rung, "message": self.message}


@dataclass
class Limits:
    inputs: int = 8
    outputs: int = 8
    memory_bits: int = 512
    timers: int = 255
    counters: int = 255


# ---------------------------------------------------------------- validation

def _is_contact(e: Any) -> bool:
    return isinstance(e, dict) and e.get("kind") in CONTACTS


def _is_branch(e: Any) -> bool:
    return isinstance(e, dict) and "branch" in e


def _is_output(e: Any) -> bool:
    return isinstance(e, dict) and (e.get("kind") in COILS or e.get("kind") in BLOCKS)


def _number(text: Any, low: int, high: int) -> int | None:
    try:
        value = int(str(text))
    except ValueError:
        return None
    return value if low <= value <= high else None


def validate(rungs: list[dict[str, Any]], symbols: dict[str, str] | None = None,
             limits: Limits | None = None) -> list[Finding]:
    limits = limits or Limits()
    findings: list[Finding] = []

    def err(i: int | None, msg: str) -> None:
        findings.append(Finding(i, msg))

    def check_bit(i: int, addr: Any, writable: bool) -> None:
        if not isinstance(addr, str):
            return err(i, f"address must be a string, got {addr!r}")
        if m := INPUT.match(addr):
            if writable:
                return err(i, f"{addr} is an input and cannot be written")
            if int(m[1]) >= limits.inputs:
                return err(i, f"{addr}: this controller has %I0.0 to %I0.{limits.inputs - 1}")
        elif m := OUTPUT.match(addr):
            if int(m[1]) >= limits.outputs:
                return err(i, f"{addr}: this controller has %Q0.0 to %Q0.{limits.outputs - 1}")
        elif m := MEMORY.match(addr):
            if int(m[1]) >= limits.memory_bits:
                return err(i, f"{addr}: memory bits are %M0 to %M{limits.memory_bits - 1}")
        elif (m := TIMER_BIT.match(addr)) or (m := COUNTER_BIT.match(addr)) or (m := SYSTEM.match(addr)):
            if writable:
                return err(i, f"{addr} is a status bit and cannot be written")
            if addr.startswith("%TM") and int(m[1]) >= limits.timers:
                return err(i, f"{addr}: timers are %TM0 to %TM{limits.timers - 1}")
            if addr.startswith("%C") and int(m[1]) >= limits.counters:
                return err(i, f"{addr}: counters are %C0 to %C{limits.counters - 1}")
        elif TIMER.match(addr) or COUNTER.match(addr):
            return err(i, f"{addr} is a function block; use its status bit (%TMn.Q, %Cn.D/.E/.F)")
        else:
            return err(i, f"{addr!r} is not an M221 bit address (%I0.x, %Q0.x, %Mn, %Sn, %TMn.Q, %Cn.D)")

    def check_args(i: int, e: dict[str, Any], low: int, high: int) -> list[Any] | None:
        args = e.get("args")
        if not isinstance(args, list) or not low <= len(args) <= high:
            want = str(low) if low == high else f"{low}..{high}"
            err(i, f"{e.get('kind')} needs {want} argument(s), got {args!r}")
            return None
        return args

    def check_note(i: int, e: dict[str, Any]) -> None:
        note = e.get("note")
        if note is not None and (not isinstance(note, str) or "\n" in note or "\r" in note):
            err(i, "note must be a single-line string")

    def check_series(i: int, items: Any, where: str, branch_first: bool = False) -> None:
        if not isinstance(items, list) or not items:
            return err(i, f"{where} must be a non-empty list")
        if not (_is_contact(items[0]) or (branch_first and _is_branch(items[0]))):
            err(i, f"{where} must start with a contact (NO, NC, RE, FE)" + (" or a branch" if branch_first else ""))
        for e in items:
            if _is_contact(e):
                if args := check_args(i, e, 1, 1):
                    check_bit(i, args[0], writable=False)
                check_note(i, e)
            elif _is_branch(e):
                check_branch(i, e)
            elif _is_output(e):
                err(i, f"{where}: outputs belong at the end of the rung, not inside a branch")
            else:
                err(i, f"unknown element {e!r}; kinds: {', '.join(KINDS)} or {{branch: [[...], [...]]}}")

    def check_branch(i: int, e: dict[str, Any]) -> None:
        legs = e["branch"]
        if not isinstance(legs, list) or len(legs) < 2:
            return err(i, "a branch needs at least two legs")
        for n, leg in enumerate(legs):
            check_series(i, leg, f"branch leg {n + 1}")

    seen_timers: dict[str, int] = {}
    seen_counters: dict[str, int] = {}
    if not isinstance(rungs, list) or not rungs:
        err(None, "rungs must be a non-empty list")
        return findings
    for i, rung in enumerate(rungs):
        if not isinstance(rung, dict) or not isinstance(rung.get("elements"), list):
            err(i, "a rung is {comment?, name?, elements: [...]}")
            continue
        for key in ("comment", "name"):
            text = rung.get(key)
            if text is not None and not isinstance(text, str):
                err(i, f"rung {key} must be a string")
        elements = rung["elements"]
        cut = len(elements)
        while cut and _is_output(elements[cut - 1]):
            cut -= 1
        logic, outputs = elements[:cut], elements[cut:]
        if not logic or not outputs:
            err(i, "a rung needs at least one contact and ends with one or more outputs")
            continue
        check_series(i, logic, "the rung", branch_first=True)
        blocks = [o for o in outputs if o["kind"] in BLOCKS]
        if blocks and len(outputs) > 1:
            err(i, "a timer or counter block must be the only output of its rung")
        for o in outputs:
            kind = o["kind"]
            check_note(i, o)
            if kind in COILS:
                if args := check_args(i, o, 1, 1):
                    check_bit(i, args[0], writable=True)
            elif kind in TIMERS:
                if not (args := check_args(i, o, 2, 3)):
                    continue
                m = TIMER.match(str(args[0]))
                if not m or int(m[1]) >= limits.timers:
                    err(i, f"{kind} needs a timer like %TM0..%TM{limits.timers - 1}, got {args[0]!r}")
                elif args[0] in seen_timers:
                    err(i, f"{args[0]} is already used by rung {seen_timers[args[0]]}")
                else:
                    seen_timers[args[0]] = i
                if _number(args[1], 1, 65535) is None:
                    err(i, f"timer preset must be an integer 1..65535, got {args[1]!r}")
                if len(args) == 3 and args[2] not in TIME_BASES:
                    err(i, f"time base must be one of {', '.join(TIME_BASES)}, got {args[2]!r}")
            else:  # CTU
                if not (args := check_args(i, o, 2, 3)):
                    continue
                m = COUNTER.match(str(args[0]))
                if not m or int(m[1]) >= limits.counters:
                    err(i, f"CTU needs a counter like %C0..%C{limits.counters - 1}, got {args[0]!r}")
                elif args[0] in seen_counters:
                    err(i, f"{args[0]} is already used by rung {seen_counters[args[0]]}")
                else:
                    seen_counters[args[0]] = i
                if _number(args[1], 1, 65535) is None:
                    err(i, f"counter preset must be an integer 1..65535, got {args[1]!r}")
                if len(args) == 3:
                    check_bit(i, args[2], writable=False)

    names: dict[str, str] = {}
    for addr, name in (symbols or {}).items():
        if not (INPUT.match(addr) or OUTPUT.match(addr) or MEMORY.match(addr)
                or TIMER.match(addr) or COUNTER.match(addr)):
            err(None, f"symbols: {addr!r} must be %I0.x, %Q0.x, %Mn, %TMn or %Cn")
        elif not isinstance(name, str) or not SYMBOL.match(name):
            err(None, f"symbols: {name!r} for {addr} must be 1-32 letters, digits or _ and not start with a digit")
        elif name.upper() in names:
            err(None, f"symbols: {name!r} is used for both {names[name.upper()]} and {addr}")
        else:
            names[name.upper()] = addr
    return findings


# ---------------------------------------------------------------- IL

def _contact(op: str, e: dict[str, Any]) -> str:
    return f"{op}{CONTACTS[e['kind']]} {e['args'][0]}"


def _series(items: list[Any], first_op: str) -> list[str]:
    """IL for contacts in series; the first one uses first_op (LD, AND(, OR()."""
    lines = [_contact(first_op, items[0])]
    for e in items[1:]:
        lines += _branch_and(e) if _is_branch(e) else [_contact("AND", e)]
    return lines


def _or_leg(leg: list[Any]) -> list[str]:
    if len(leg) == 1:
        return [_contact("OR", leg[0])]
    return _series(leg, "OR(") + [")"]


def _branch_and(e: dict[str, Any]) -> list[str]:
    legs = e["branch"]
    lines = _series(legs[0], "AND(")
    for leg in legs[1:]:
        lines += _or_leg(leg)
    return lines + [")"]


def _logic(items: list[Any]) -> list[str]:
    first = items[0]
    if _is_branch(first):
        lines = _series(first["branch"][0], "LD")
        for leg in first["branch"][1:]:
            lines += _or_leg(leg)
    else:
        lines = [_contact("LD", first)]
    for e in items[1:]:
        lines += _branch_and(e) if _is_branch(e) else [_contact("AND", e)]
    return lines


def rung_il(rung: dict[str, Any]) -> list[str]:
    elements = rung["elements"]
    cut = len(elements)
    while cut and _is_output(elements[cut - 1]):
        cut -= 1
    logic, outputs = _logic(elements[:cut]), elements[cut:]
    first = outputs[0]
    if first["kind"] in TIMERS:
        return [f"BLK {first['args'][0]}", *logic, "IN", "END_BLK"]
    if first["kind"] == "CTU":
        reset = [f"LD {first['args'][2]}", "R"] if len(first["args"]) == 3 else []
        return [f"BLK {first['args'][0]}", *reset, *logic, "CU", "END_BLK"]
    return logic + [f"{COILS[o['kind']]} {o['args'][0]}" for o in outputs]


def expected_il(rungs: list[dict[str, Any]]) -> list[list[str]]:
    return [rung_il(r) for r in rungs]


def normalize_il(line: str) -> str:
    """Machine Expert - Basic pads the operator column on save ("LD    %I0.0")."""
    return " ".join(line.split())


# ---------------------------------------------------------------- .smbp I/O

def read_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    if not raw.startswith(b"\xef\xbb\xbf<?xml"):
        raise FormatError(f"{path} is not a Machine Expert - Basic project (UTF-8 BOM XML expected)")
    return raw[3:].decode("utf-8")


def parse(text: str) -> ET.Element:
    root = ET.fromstring(text.encode("utf-8"))
    if root.tag != "ProjectDescriptor" or root.find("SoftwareConfiguration/Pous") is None:
        raise FormatError("not a Machine Expert - Basic project (no ProjectDescriptor/SoftwareConfiguration/Pous)")
    return root


def encode(root: ET.Element, original: str) -> bytes:
    """Serialize like XmlSerializer: 2-space indent, CRLF, original declaration and root tag."""
    ET.indent(root, "  ")
    body = ET.tostring(root, encoding="unicode")
    start = original.index("<ProjectDescriptor")
    root_tag = original[start:original.index(">", start) + 1]
    body = re.sub(r"^<ProjectDescriptor[^>]*>", lambda _: root_tag, body, count=1)
    text = original[:start] + body
    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    if original.endswith("\r\n"):
        text += "\r\n"
    return b"\xef\xbb\xbf" + text.encode("utf-8")


def limits_of(root: ET.Element) -> Limits:
    cpu = root.find("HardwareConfiguration/Plc/Cpu")
    limits = Limits()
    if cpu is not None:
        limits.inputs = len(cpu.findall("DigitalInputs/DiscretInput")) or limits.inputs
        limits.outputs = len(cpu.findall("DigitalOutputs/DiscretOutput")) or limits.outputs
        for tag, attr in (("TimersMax", "timers"), ("CountersMax", "counters")):
            found = cpu.find(f".//{tag}")
            if found is not None and (found.text or "").isdigit():
                setattr(limits, attr, int(found.text))
    forced = root.find("SoftwareConfiguration/MemoryBitsMemoryAllocation/ForcedCount")
    if forced is not None and (forced.text or "").isdigit():
        limits.memory_bits = int(forced.text)
    return limits


def _sub(parent: ET.Element, tag: str, text: str | None = None) -> ET.Element:
    e = ET.SubElement(parent, tag)
    e.text = text
    return e


def _set_child(entry: ET.Element, tag: str, text: str | None, after: tuple[str, ...]) -> None:
    """Set/remove a child, keeping XmlSerializer member order (insert after the last of `after`)."""
    found = entry.find(tag)
    if not text:
        if found is not None:
            entry.remove(found)
        return
    if found is None:
        position = 0
        for n, child in enumerate(list(entry)):
            if child.tag in after:
                position = n + 1
        found = ET.Element(tag)
        entry.insert(position, found)
    found.text = text


def _ensure(parent: ET.Element, tag: str, address: str, index: int) -> ET.Element:
    for entry in parent.findall(tag):
        if entry.findtext("Address") == address:
            return entry
    entry = ET.Element(tag)
    _sub(entry, "Address", address)
    _sub(entry, "Index", str(index))
    entries = parent.findall(tag)
    position = sum(1 for e in entries if int(e.findtext("Index") or 0) < index)
    parent.insert(position, entry)
    return entry


def _annotations(rungs: list[dict[str, Any]]) -> dict[str, str]:
    notes: dict[str, str] = {}

    def walk(items: list[Any]) -> None:
        for e in items:
            if _is_branch(e):
                for leg in e["branch"]:
                    walk(leg)
            elif e.get("note"):
                addr = e["args"][0]
                notes.setdefault(re.sub(r"\.(Q|D|E|F)$", "", addr), e["note"])

    for r in rungs:
        walk(r["elements"])
    return notes


def _rung_xml(rung: dict[str, Any]) -> ET.Element:
    entity = ET.Element("RungEntity")
    ET.SubElement(entity, "LadderElements")
    lines = _sub(entity, "InstructionLines")
    for text in rung_il(rung):
        line = _sub(lines, "InstructionLineEntity")
        _sub(line, "InstructionLine", text)
        ET.SubElement(line, "Comment")
    for tag, value in (("Name", rung.get("name")), ("MainComment", rung.get("comment")), ("Label", None)):
        _sub(entity, tag, value or None)
    _sub(entity, "IsLadderSelected", "false")
    return entity


def apply_program(root: ET.Element, rungs: list[dict[str, Any]] | None, symbols: dict[str, str],
                  name: str, full_name: str) -> None:
    """Replace the first POU's rungs (None keeps them) and set name, presets and symbols."""
    sw = root.find("SoftwareConfiguration")
    pou = sw.find("Pous/ProgramOrganizationUnits")
    if pou is None:
        raise FormatError("the project has no POU")
    for tag, value in (("Name", name), ("FullName", full_name)):
        found = root.find(tag)
        if found is not None:
            found.text = value
    if rungs is None:
        return
    old = pou.find("Rungs")
    position = list(pou).index(old)
    pou.remove(old)
    new = ET.Element("Rungs")
    for rung in rungs:
        new.append(_rung_xml(rung))
    pou.insert(position, new)

    # timers and counters configured by the blocks
    timers, counters = sw.find("Timers"), sw.find("Counters")
    for rung in rungs:
        block = rung["elements"][-1]
        if block.get("kind") in TIMERS:
            addr, preset = block["args"][0], str(int(block["args"][1]))
            base = TIME_BASES[block["args"][2] if len(block["args"]) == 3 else "1s"]
            entry = _ensure(timers, "TimerTM", addr, int(TIMER.match(addr)[1]))
            _set_child(entry, "Type", TIMERS[block["kind"]], ("Address", "Index", "Symbol", "Comment"))
            _set_child(entry, "Preset", preset, ("Address", "Index", "Symbol", "Comment", "Type"))
            _set_child(entry, "Base", base, ("Address", "Index", "Symbol", "Comment", "Type", "Preset"))
        elif block.get("kind") == "CTU":
            addr = block["args"][0]
            entry = _ensure(counters, "Counter", addr, int(COUNTER.match(addr)[1]))
            _set_child(entry, "Preset", str(int(block["args"][1])), ("Address", "Index", "Symbol", "Comment"))

    # symbols and comments
    notes = _annotations(rungs)
    cpu = root.find("HardwareConfiguration/Plc/Cpu")
    for addr in sorted(set(symbols) | set(notes)):
        if m := INPUT.match(addr):
            entry = _ensure(cpu.find("DigitalInputs"), "DiscretInput", addr, int(m[1]))
        elif m := OUTPUT.match(addr):
            entry = _ensure(cpu.find("DigitalOutputs"), "DiscretOutput", addr, int(m[1]))
        elif m := MEMORY.match(addr):
            entry = _ensure(sw.find("MemoryBits"), "MemoryBit", addr, int(m[1]))
        elif m := TIMER.match(addr):
            entry = _ensure(timers, "TimerTM", addr, int(m[1]))
        elif m := COUNTER.match(addr):
            entry = _ensure(counters, "Counter", addr, int(m[1]))
        else:
            continue  # %S system bits keep their built-in names
        _set_child(entry, "Symbol", symbols.get(addr), ("Address", "Index"))
        _set_child(entry, "Comment", notes.get(addr), ("Address", "Index", "Symbol"))


def win_path(path: str) -> str:
    """WSL /mnt/<d>/... -> D:\\...; Windows paths pass through."""
    if path.startswith("/mnt/") and len(path) > 6 and path[6] == "/":
        return f"{path[5].upper()}:\\" + path[7:].replace("/", "\\")
    return path


def write_project(path: Path, base: Path, rungs: list[dict[str, Any]] | None, symbols: dict[str, str],
                  target: Path | None = None) -> None:
    """Write `base` with the rungs to `path`; Name/FullName describe `target` (default `path`)."""
    original = read_text(base)
    root = parse(original)
    target = (target or path).resolve()
    apply_program(root, rungs, symbols, target.stem, win_path(str(target)))
    path.write_bytes(encode(root, original))


def read_project(path: str | Path) -> dict[str, Any]:
    root = parse(read_text(path))
    sw = root.find("SoftwareConfiguration")
    pous = []
    for pou in sw.findall("Pous/ProgramOrganizationUnits"):
        rungs = []
        for r in pou.findall("Rungs/RungEntity"):
            rungs.append({
                "name": r.findtext("Name") or "",
                "comment": r.findtext("MainComment") or "",
                "il": [normalize_il(e.findtext("InstructionLine") or "") for e in r.findall("InstructionLines/InstructionLineEntity")],
                "ladder": r.findtext("IsLadderSelected") == "true" and len(r.find("LadderElements") or []) > 0,
            })
        pous.append({"name": pou.findtext("Name") or "", "rungs": rungs})
    symbols, comments = {}, {}
    cpu = root.find("HardwareConfiguration/Plc/Cpu")
    entries = [*cpu.findall("DigitalInputs/DiscretInput"), *cpu.findall("DigitalOutputs/DiscretOutput"),
               *sw.findall("MemoryBits/MemoryBit"), *sw.findall("Timers/TimerTM"), *sw.findall("Counters/Counter")]
    for e in entries:
        if e.findtext("Symbol"):
            symbols[e.findtext("Address")] = e.findtext("Symbol")
        if e.findtext("Comment"):
            comments[e.findtext("Address")] = e.findtext("Comment")
    base_names = {v: k for k, v in TIME_BASES.items()}
    timers = [{"address": t.findtext("Address"), "type": t.findtext("Type") or "TON",
               "preset": int(t.findtext("Preset") or 0), "base": base_names.get(t.findtext("Base") or "", t.findtext("Base"))}
              for t in sw.findall("Timers/TimerTM") if t.find("Preset") is not None]
    counters = [{"address": c.findtext("Address"), "preset": int(c.findtext("Preset") or 0)}
                for c in sw.findall("Counters/Counter") if c.find("Preset") is not None]
    return {"name": root.findtext("Name"), "cpu": cpu.findtext("Reference") if cpu is not None else None,
            "pous": pous, "timers": timers, "counters": counters, "symbols": symbols, "comments": comments}


def compare(path: str | Path, rungs: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare the first POU's IL in a project file with the IL expected for `rungs`."""
    got = [r["il"] for r in read_project(path)["pous"][0]["rungs"]]
    want = expected_il(rungs)
    diffs = [{"rung": i, "expected": w, "found": g}
             for i, (w, g) in enumerate(zip(want, got)) if w != g]
    if len(got) != len(want):
        diffs.append({"rung": None, "expected": f"{len(want)} rungs", "found": f"{len(got)} rungs"})
    return {"il_matches": not diffs, "differences": diffs}
