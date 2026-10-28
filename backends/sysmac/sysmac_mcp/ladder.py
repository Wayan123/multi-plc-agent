"""Rung JSON -> IEC 61131-10 XML (Sysmac Studio dialect) and read-back of Sysmac's stored ladder listing.

Rung JSON (same shape as the other backends, IEC names like the CODESYS backend):
    {"comment": "Run request",
     "elements": [
        {"branch": [[{"kind": "NO", "args": ["Start"]}], [{"kind": "NO", "args": ["Run"]}]]},
        {"kind": "NC", "args": ["StopPB"]},
        {"kind": "OUT", "args": ["Run"]}]}

Outputs (last element, one per rung):
    OUT/SET/RST [bool]               coil
    TON/TOF/TP  [instance, TIME]      e.g. ["StartDelay", "T#3s"]; contacts read "StartDelay.Q"
    CTU         [instance, PV, reset] e.g. ["Batch", "10", "CountReset"]; contacts read "Batch.Q"

Variables are program-local: [{"name", "type"?: "BOOL"|"INT"|..., "comment"?}]. Timer/counter
instances are declared from the rungs that use them.

Read-back: after Sysmac Studio saves, each ladder section is stored under
C:\\OMRON\\Data\\Solution\\<project-id>\\<section-id>.xml as a JSON listing of compiled
instructions ({"CLs": [{"__type": "LD", "Var": "a"}, {"__type": "ST", "Var": "b"}, ...]}).
parse_listing() turns that listing back into per-rung logic so it can be compared with
expected_logic() of the rung JSON.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape, quoteattr

NS = "www.iec.ch/public/TC65SC65BWG7TF10"
SMC = "https://www.ia.omron.com/Smc IEC61131_10_Ed1_0_SmcExt1_0_Spc1_0.xsd"

CONTACTS = ("NO", "NC")
COILS = ("OUT", "SET", "RST")
TIMERS = ("TON", "TOF", "TP")
OUTPUTS = COILS + TIMERS + ("CTU",)
ARITY = {"NO": 1, "NC": 1, "OUT": 1, "SET": 1, "RST": 1, "TON": 2, "TOF": 2, "TP": 2, "CTU": 3}
TYPES = ("BOOL", "INT", "UINT", "DINT", "WORD", "DWORD", "REAL", "TIME")
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
MEMBER = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.Q$")
TIME = re.compile(r"^T#(\d+(ms|MS|s|S|m|M|h|H))+$")
RESERVED = {"AND", "OR", "NOT", "XOR", "MOD", "TRUE", "FALSE", "IF", "THEN", "ELSE", "END_IF", "VAR",
            "END_VAR", "PROGRAM", "AT", "TON", "TOF", "TP", "CTU", "CTD", "R_TRIG", "F_TRIG", "TIMER"}


@dataclass
class Finding:
    level: str
    rung: int | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"level": self.level, "rung": self.rung, "message": self.message}


def instances(rungs: list[dict[str, Any]]) -> dict[str, str]:
    found: dict[str, str] = {}
    for rung in rungs:
        out = rung["elements"][-1]
        if out.get("kind") in TIMERS + ("CTU",):
            found.setdefault(str(out["args"][0]), out["kind"])
    return found


def validate(program: str, variables: list[dict[str, Any]], rungs: list[dict[str, Any]]) -> list[Finding]:
    out: list[Finding] = []

    def err(i: int | None, msg: str) -> None:
        out.append(Finding("error", i, msg))

    if not IDENT.match(program or "") or program.upper() in RESERVED:
        err(None, f"program name {program!r} is not a valid identifier")
    declared: dict[str, str] = {}
    for v in variables:
        name, vtype = str(v.get("name", "")), str(v.get("type", "BOOL")).upper()
        if not IDENT.match(name) or name.upper() in RESERVED or name.startswith("_"):
            err(None, f"variable {name!r}: not a valid Sysmac identifier (no leading underscore)")
            continue
        if name.lower() in (n.lower() for n in declared):
            err(None, f"variable {name!r}: declared twice (names are case-insensitive)")
        if vtype not in TYPES:
            err(None, f"variable {name!r}: type must be one of {list(TYPES)}")
        if v.get("comment") is not None and not isinstance(v["comment"], str):
            err(None, f"variable {name!r}: comment must be a string")
        declared[name] = vtype
    if not rungs:
        err(None, "no rungs")
        return out
    try:
        fbs = instances(rungs)
    except (KeyError, IndexError, TypeError, AttributeError):
        fbs = {}
    for name, kind in fbs.items():
        if name.lower() in (n.lower() for n in declared):
            err(None, f"{kind} instance {name!r} clashes with a declared variable")
        if not IDENT.match(name) or name.upper() in RESERVED:
            err(None, f"{kind} instance {name!r}: not a valid identifier")

    def is_bool(ref: str) -> bool:
        m = MEMBER.match(ref)
        return m.group(1) in fbs if m else declared.get(ref) == "BOOL"

    for i, rung in enumerate(rungs):
        if not isinstance(rung, dict) or not isinstance(rung.get("elements"), list):
            err(i, "rung must be {comment?, elements: [...]}")
            continue
        elems = rung["elements"]
        if len(elems) < 2:
            err(i, "a rung needs at least one contact and one output")
            continue
        *inputs, output = elems

        def series(elements: list[Any], where: str) -> None:
            for j, e in enumerate(elements):
                if isinstance(e, dict) and "branch" in e:
                    legs = e["branch"]
                    if not isinstance(legs, list) or len(legs) < 2:
                        err(i, f"{where}{j}: a branch needs at least two legs")
                        continue
                    for k, leg in enumerate(legs):
                        if not isinstance(leg, list) or not leg:
                            err(i, f"{where}{j} leg {k}: empty leg")
                        else:
                            series(leg, f"{where}{j} leg {k} element ")
                elif not isinstance(e, dict) or e.get("kind") not in CONTACTS:
                    err(i, f"{where}{j}: expected a contact NO|NC or a branch, got {e!r}")
                elif len(e.get("args") or []) != 1 or not is_bool(str(e["args"][0])):
                    err(i, f"{where}{j}: contact needs one declared BOOL or <instance>.Q (got {e.get('args')!r})")

        series(inputs, "element ")
        kind = output.get("kind") if isinstance(output, dict) else None
        if kind not in OUTPUTS:
            err(i, f"last element must be one of {list(OUTPUTS)} (got {kind!r})")
            continue
        args = [str(a) for a in output.get("args") or []]
        if len(args) != ARITY[kind]:
            err(i, f"{kind} takes {ARITY[kind]} args, got {args!r}")
            continue
        if kind in COILS and declared.get(args[0]) != "BOOL":
            err(i, f"{kind} target {args[0]!r} must be a declared BOOL variable")
        if kind in TIMERS and not TIME.match(args[1]):
            err(i, f"{kind} preset must be a TIME literal like T#3s, got {args[1]!r}")
        if kind == "CTU":
            if not args[1].isdigit() or not 0 < int(args[1]) <= 32767:
                err(i, f"CTU preset must be an integer 1..32767, got {args[1]!r}")
            if not is_bool(args[2]):
                err(i, f"CTU reset {args[2]!r} must be a declared BOOL or <instance>.Q")
    return out


# --- IEC 61131-10 XML ------------------------------------------------------------

def _smc(inner: str) -> str:
    return f'<AddData><Data name="{SMC}" handleUnknown="discard">{inner}</Data></AddData>'


def _cin(refs: list[int], order: int | None = None) -> str:
    extra = _smc(f'<smcext:ConnectionPointInOrder order="{order}" />') if order else ""
    return "<ConnectionPointIn>" + extra + "".join(f'<Connection refConnectionPointOutId="{r}" />' for r in refs) + "</ConnectionPointIn>"


def _cout(i: int, order: int | None = None) -> str:
    if order:
        return f'<ConnectionPointOut connectionPointOutId="{i}">' + _smc(f'<smcext:ConnectionPointOutOrder order="{order}" />') + "</ConnectionPointOut>"
    return f'<ConnectionPointOut connectionPointOutId="{i}" />'


def _rung(n: int, rung: dict[str, Any]) -> str:
    ids = iter(range(1, 10_000))
    parts: list[str] = []
    if rung.get("comment"):
        parts.append(f'<CommonObject xsi:type="Comment"><Content xsi:type="SimpleText">{escape(rung["comment"])}</Content></CommonObject>')
    rail = next(ids)
    parts.append(f'<LdObject xsi:type="LeftPowerRail">{_cout(rail)}</LdObject>')
    *inputs, output = rung["elements"]

    def series(elements: list[dict[str, Any]], ends: list[int]) -> list[int]:
        for e in elements:
            if "branch" in e:
                legs: list[int] = []
                for leg in e["branch"]:
                    legs += series(leg, ends)
                ends = legs
            else:
                i = next(ids)
                neg = ' negated="true"' if e["kind"] == "NC" else ""
                parts.append(f'<LdObject xsi:type="Contact"{neg} operand={quoteattr(str(e["args"][0]))}>{_cin(ends)}{_cout(i)}</LdObject>')
                ends = [i]
        return ends

    ends = series(inputs, [rail])
    kind, args = output["kind"], [str(a) for a in output["args"]]
    if kind in COILS:
        i = next(ids)
        latch = {"OUT": "", "SET": ' latch="set"', "RST": ' latch="reset"'}[kind]
        parts.append(f'<LdObject xsi:type="Coil"{latch} operand={quoteattr(args[0])}>{_cin(ends)}{_cout(i)}</LdObject>')
        right = [i]
    else:
        if kind in TIMERS:
            names, consts, sinks = ("In", "PT"), [args[1]], [("Q", 1), ("ET", 2)]
        else:
            names, consts, sinks = ("CU", "Reset", "PV"), [args[2], f"INT#{args[1]}"], [("Q", 1), ("CV", 2)]
        src_ids = []
        for c in consts:
            s = next(ids)
            src_ids.append(s)
            parts.append(f'<FbdObject xsi:type="DataSource" identifier={quoteattr(c)}>{_cout(s)}</FbdObject>')
        ins = f'<InputVariable parameterName="{names[0]}">{_cin(ends, 1)}</InputVariable>'
        for k, (pname, s) in enumerate(zip(names[1:], src_ids), start=2):
            ins += f'<InputVariable parameterName="{pname}">{_cin([s], k)}</InputVariable>'
        out_ids = {p: next(ids) for p, _ in sinks}
        outs = "".join(f'<OutputVariable parameterName="{p}">{_cout(out_ids[p], o)}</OutputVariable>' for p, o in sinks)
        parts.append(f'<FbdObject xsi:type="Block" typeName="{kind}" instanceName={quoteattr(args[0])}>'
                     f"<InputVariables>{ins}</InputVariables><OutputVariables>{outs}</OutputVariables></FbdObject>")
        for p, _ in sinks[1:]:
            parts.append(f'<FbdObject xsi:type="DataSink" identifier="">{_cin([out_ids[p]])}</FbdObject>')
        right = [out_ids["Q"]]
    parts.append(f'<LdObject xsi:type="RightPowerRail">{_cin(right)}</LdObject>')
    return f'<Rung evaluationOrder="{n}">' + "".join(parts) + "</Rung>"


def _var(name: str, vtype: str, comment: str | None = None) -> str:
    doc = f'<Documentation xsi:type="SimpleText">{escape(comment)}</Documentation>' if comment else ""
    return f'<Variable name={quoteattr(name)}>{doc}<Type><TypeName>{escape(vtype)}</TypeName></Type></Variable>'


def to_iec_xml(program: str, variables: list[dict[str, Any]], rungs: list[dict[str, Any]],
               model: str = "NX1P2-1040DT", version: str = "1.47") -> str:
    decls = [_var(v["name"], str(v.get("type", "BOOL")).upper(), v.get("comment")) for v in variables]
    decls += [_var(n, k) for n, k in instances(rungs).items()]
    body = "".join(_rung(i + 1, r) for i, r in enumerate(rungs))
    return ('<?xml version="1.0" encoding="utf-8"?>\n'
            '<Project xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:smcext="https://www.ia.omron.com/Smc" '
            'xsi:schemaLocation="https://www.ia.omron.com/Smc IEC61131_10_Ed1_0_SmcExt1_0_Spc1_0.xsd" schemaVersion="1" '
            f'xmlns="{NS}">'
            '<FileHeader companyName="multi-plc-agent" productName="sysmac_mcp" productVersion="0.1.0" />'
            f'<ContentHeader name={quoteattr(program)} creationDateTime="2000-01-01T00:00:00">'
            f'<AddDataInfo><Info name="{SMC}" vendor="https://www.ia.omron.com/Smc" /></AddDataInfo>'
            + _smc(f'<smcext:DeviceInfo modelName={quoteattr(model)} version={quoteattr(version)} />') +
            '</ContentHeader><Types><GlobalNamespace>'
            f'<Program name={quoteattr(program)}><Vars accessSpecifier="private">{"".join(decls)}</Vars>'
            f'<MainBody><BodyContent xsi:type="smcext:LdSection" name="Section0" evaluationOrder="1">{body}</BodyContent></MainBody>'
            '</Program></GlobalNamespace></Types>'
            '<Instances><Configuration name="Configuration"><Resource name="Resource" resourceTypeName="" /></Configuration></Instances>'
            '</Project>\n')


# --- logic signature (rung JSON vs. Sysmac's stored listing) ----------------------

def _dnf(e: Any) -> frozenset:
    if isinstance(e, str):
        return frozenset({frozenset()}) if e == "TRUE" else frozenset({frozenset({e})})
    if e[0] == "FALSE":
        return frozenset()
    if e[0] == "OR":
        return frozenset().union(*(_dnf(x) for x in e[1:]))
    out = frozenset({frozenset()})
    for x in e[1:]:
        out = frozenset(a | b for a in out for b in _dnf(x))
    return out


def render(e: Any) -> str:
    """Canonical sum-of-products text; equal logic gives equal text."""
    terms = sorted(" AND ".join(sorted(t)) or "TRUE" for t in _dnf(e))
    return " OR ".join(f"({t})" if " AND " in t and len(terms) > 1 else t for t in terms) or "FALSE"


def _lit(name: str, negated: bool) -> str:
    return f"NOT {name}" if negated else name


def _series(elements: list[dict[str, Any]]) -> Any:
    terms: list[Any] = []
    for e in elements:
        if "branch" in e:
            terms.append(("OR", *[_series(leg) for leg in e["branch"]]))
        else:
            terms.append(_lit(str(e["args"][0]), e["kind"] == "NC"))
    return ("AND", *terms) if terms else "TRUE"


def expected_logic(rungs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for rung in rungs:
        *inputs, output = rung["elements"]
        kind, args = output["kind"], [str(a) for a in output["args"]]
        item = {"comment": rung.get("comment") or "", "kind": kind, "target": args[0], "logic": render(_series(inputs))}
        if kind in TIMERS:
            item["params"] = {"PT": args[1]}
        if kind == "CTU":
            item["params"] = {"PV": f"INT#{args[1]}", "Reset": args[2]}
        out.append(item)
    return out


def parse_listing(text: str) -> list[dict[str, Any]]:
    """Logic per rung from a stored Sysmac ladder section (one JSON object per line).

    Each object lists cells CLs (LD contact, HL horizontal wire, ST coil with S/RS latch flags,
    FB block) placed on a grid by X (column, default 0) and Y (row, default 0), plus vertical
    links VLs at column X joining row Y (default 0) to row Y+H (H default 1). Power flows left
    to right along a row; rows touched by connected vertical links at a column share OR-ed power.
    """
    rungs = []
    for line in text.lstrip("\ufeff").splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        cells = {(c.get("X", 0), c.get("Y", 0)): c for c in r.get("CLs", [])}
        rows = sorted({y for _, y in cells} | {v.get("Y", 0) + v.get("H", 1) for v in r.get("VLs", [])} | {0})
        width = max([x for x, _ in cells] + [0]) + 1
        links = [(v.get("X", 0), v.get("Y", 0), v.get("Y", 0) + v.get("H", 1)) for v in r.get("VLs", [])]
        power: dict[int, Any] = {y: ("TRUE" if (0, y) in cells or y == 0 else ("FALSE",)) for y in rows}
        output = None
        for x in range(width + 1):
            groups: list[set[int]] = []
            for lx, y0, y1 in links:
                if lx != x:
                    continue
                span = {y for y in rows if y0 <= y <= y1}
                for g in [g for g in groups if g & span]:
                    span |= g
                    groups.remove(g)
                groups.append(span)
            for g in groups:
                joined = ("OR", *[power[y] for y in sorted(g)])
                for y in g:
                    power[y] = joined
            if x == width:
                break
            for y in rows:
                c = cells.get((x, y))
                if c is None:
                    continue
                t = c["__type"]
                if t == "LD":
                    power[y] = ("AND", power[y], _lit(c["Var"], bool(c.get("Not"))))
                elif t != "HL":
                    output = (c, power[y])
        if output is None:
            raise ValueError(f"rung without output: {line[:120]}")
        c, logic = output
        t = c["__type"]
        if t == "FB":
            prm = {p["Arg"]: p.get("Var", "") for p in c.get("In", []) if p.get("__type") == "PRM"}
            item = {"comment": r.get("CMT", ""), "kind": c["Name"], "target": c["Var"], "logic": render(logic), "params": prm}
        else:
            kind = "SET" if c.get("S") else "RST" if c.get("RS") else "OUT"
            item = {"comment": r.get("CMT", ""), "kind": kind, "target": c["Var"], "logic": render(logic)}
        rungs.append(item)
    return rungs


def program_entity_pattern(program: str) -> re.Pattern:
    """Regex for a Program entity in a Sysmac .oem project index.

    The Solution entity carries the project name, which can equal a program name, so the
    lookup must anchor on type="Program" rather than on name="..." alone.
    """
    return re.compile(r'<Entity type="Program" subtype="\w+" id="[0-9a-f-]+" name="%s"' % re.escape(program))
