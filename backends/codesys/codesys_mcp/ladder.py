"""Rung JSON -> PLCopen XML (CODESYS LD dialect) and back to logic for verification.

Rung JSON:
    {"comment": "Run request",
     "elements": [
        {"branch": [[{"kind": "NO", "args": ["Start"]}], [{"kind": "NO", "args": ["Run"]}]]},
        {"kind": "NC", "args": ["StopPB"]},
        {"kind": "OUT", "args": ["Run"]}]}

Outputs (last element, exactly one per rung):
    OUT/SET/RST [bool]            coil; SET/RST are latching coils
    TON/TOF/TP  [instance, TIME]  e.g. ["StartDelay", "T#3S"]; contacts use "StartDelay.Q"
    CTU         [instance, PV, reset_bool]  e.g. ["Batch", "10", "CountReset"]; contacts use "Batch.Q"

Variables are declared explicitly: [{"name", "type": "BOOL"|"INT"|..., "address"?: "%IX0.0", "comment"?}].
Timer and counter instances are declared automatically from the rungs that use them.

The verification compares logic, not XML: each network becomes
(output kind, target, boolean expression[, parameters]) both from the rung JSON
and from the PLCopen XML that CODESYS exports after import, so localId
renumbering or layout data added by CODESYS does not matter.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

PLCOPEN = "http://www.plcopen.org/xml/tc6_0200"
XHTML = "http://www.w3.org/1999/xhtml"
PLAINTEXT = "http://www.3s-software.com/plcopenxml/interfaceasplaintext"
ELEMENT_TYPE = "http://www.3s-software.com/plcopenxml/fbdelementtype"
RIGHT_RAIL = 2147483646

CONTACTS = ("NO", "NC")
COILS = ("OUT", "SET", "RST")
TIMERS = ("TON", "TOF", "TP")
OUTPUTS = COILS + TIMERS + ("CTU",)
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
MEMBER = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\.(Q)$")
ADDRESS = re.compile(r"^%[IQM]X\d+\.[0-7]$|^%[IQM][BWD]\d+$")
TIME = re.compile(r"^T#(\d+(ms|MS|s|S|m|M|h|H))+$")
TYPES = ("BOOL", "INT", "UINT", "DINT", "WORD", "DWORD", "REAL", "TIME")
KEYWORDS = {"AND", "OR", "NOT", "XOR", "MOD", "TRUE", "FALSE", "IF", "THEN", "ELSE", "END_IF",
            "VAR", "END_VAR", "PROGRAM", "END_PROGRAM", "AT", "TON", "TOF", "TP", "CTU", "CTD", "R_TRIG", "F_TRIG"}


@dataclass
class Finding:
    level: str
    rung: int | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"level": self.level, "rung": self.rung, "message": self.message}


def _one_line(text: Any) -> bool:
    return isinstance(text, str) and "\n" not in text and "\r" not in text and "*)" not in text


def instances(rungs: list[dict[str, Any]]) -> dict[str, str]:
    """Timer/counter instance name -> FB type, in first-use order."""
    found: dict[str, str] = {}
    for rung in rungs:
        out = rung["elements"][-1]
        if out.get("kind") in TIMERS + ("CTU",):
            found.setdefault(str(out["args"][0]), out["kind"])
    return found


def validate(pou: str, variables: list[dict[str, Any]], rungs: list[dict[str, Any]]) -> list[Finding]:
    out: list[Finding] = []

    def err(i: int | None, msg: str) -> None:
        out.append(Finding("error", i, msg))

    if not IDENT.match(pou or "") or pou.upper() in KEYWORDS:
        err(None, f"POU name {pou!r} is not a valid IEC identifier")
    declared: dict[str, str] = {}
    for v in variables:
        name, vtype = v.get("name", ""), str(v.get("type", "BOOL")).upper()
        if not IDENT.match(name) or name.upper() in KEYWORDS:
            err(None, f"variable {name!r}: not a valid IEC identifier")
            continue
        if name.lower() in (n.lower() for n in declared):
            err(None, f"variable {name!r}: declared twice (IEC names are case-insensitive)")
        if vtype not in TYPES:
            err(None, f"variable {name!r}: type must be one of {list(TYPES)}")
        if v.get("address") is not None and not ADDRESS.match(str(v["address"])):
            err(None, f"variable {name!r}: address {v['address']!r} must look like %IX0.0, %QX0.1, %MX1.2 or %MW10")
        if v.get("comment") is not None and not _one_line(v["comment"]):
            err(None, f"variable {name!r}: comment must be one line without '*)'")
        declared[name] = vtype
    if not rungs:
        err(None, "no rungs")
        return out
    try:
        fbs = instances(rungs)
    except (KeyError, IndexError, TypeError, AttributeError):
        fbs = {}
    for name, kind in fbs.items():
        if name in declared:
            err(None, f"{kind} instance {name!r} clashes with a declared variable")
        if not IDENT.match(name) or name.upper() in KEYWORDS:
            err(None, f"{kind} instance {name!r}: not a valid IEC identifier")

    def is_bool(ref: str) -> bool:
        m = MEMBER.match(ref)
        if m:
            return m.group(1) in fbs
        return declared.get(ref) == "BOOL"

    def check_contact(i: int, c: Any, where: str) -> None:
        if not isinstance(c, dict) or c.get("kind") not in CONTACTS:
            err(i, f"{where}: expected a contact {{kind: NO|NC, args: [name]}}, got {c!r}")
            return
        args = c.get("args") or []
        if len(args) != 1 or not is_bool(str(args[0])):
            err(i, f"{where}: contact needs one declared BOOL variable or <timer/counter>.Q (got {args!r})")

    for i, rung in enumerate(rungs):
        if not isinstance(rung, dict) or not isinstance(rung.get("elements"), list):
            err(i, "rung must be {comment?, elements: [...]}")
            continue
        if rung.get("comment") is not None and not isinstance(rung["comment"], str):
            err(i, "rung comment must be a string")
        elems = rung["elements"]
        if len(elems) < 2:
            err(i, "a rung needs at least one contact and one output")
            continue
        *inputs, output = elems

        def check_series(elements: list[Any], where: str) -> None:
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
                            check_series(leg, f"{where}{j} leg {k} element ")
                else:
                    check_contact(i, e, f"{where}{j}")

        check_series(inputs, "element ")
        kind = output.get("kind") if isinstance(output, dict) else None
        if kind not in OUTPUTS:
            err(i, f"last element must be one of {list(OUTPUTS)} (got {kind!r}); one output per rung")
            continue
        args = [str(a) for a in output.get("args") or []]
        need = {"TON": 2, "TOF": 2, "TP": 2, "CTU": 3}.get(kind, 1)
        if len(args) != need:
            err(i, f"{kind} takes {need} args, got {args!r}")
            continue
        if kind in COILS:
            if declared.get(args[0]) != "BOOL":
                err(i, f"{kind} target {args[0]!r} must be a declared BOOL variable")
            elif str(next((v.get("address", "") for v in variables if v.get("name") == args[0]), "") or "").startswith("%I"):
                err(i, f"{kind} target {args[0]!r} is mapped to an input address")
        if kind in TIMERS and not TIME.match(args[1]):
            err(i, f"{kind} preset must be an IEC TIME literal like T#3S or T#500MS, got {args[1]!r}")
        if kind == "CTU":
            if not args[1].isdigit() or not 0 < int(args[1]) <= 32767:
                err(i, f"CTU preset must be an integer 1..32767, got {args[1]!r}")
            if not is_bool(args[2]):
                err(i, f"CTU reset {args[2]!r} must be a declared BOOL variable or <timer/counter>.Q")
    return out


def declaration(pou: str, variables: list[dict[str, Any]], rungs: list[dict[str, Any]]) -> str:
    lines = [f"PROGRAM {pou}", "VAR"]
    for v in variables:
        at = f" AT {v['address']}" if v.get("address") else ""
        note = f" // {v['comment']}" if v.get("comment") else ""
        lines.append(f"\t{v['name']}{at} : {str(v.get('type', 'BOOL')).upper()};{note}")
    for name, kind in instances(rungs).items():
        lines.append(f"\t{name} : {kind};")
    lines += ["END_VAR", ""]
    return "\n".join(lines)


class _Ids:
    def __init__(self) -> None:
        self.n = 0

    def next(self) -> int:
        self.n += 1
        return self.n


def _x(text: str) -> str:
    return f'<xhtml xmlns="{XHTML}">{escape(text)}</xhtml>'


def _conn(refs: list[tuple[int, str | None]]) -> str:
    return "".join(f'<connection refLocalId="{r}"' + (f' formalParameter="{p}"' if p else "") + "/>" for r, p in refs)


def _contact(i: int, c: dict[str, Any], refs: list[tuple[int, str | None]]) -> str:
    return (f'<contact localId="{i}" negated="{"true" if c["kind"] == "NC" else "false"}" storage="none" edge="none">'
            f'<position x="0" y="0"/><connectionPointIn>{_conn(refs)}</connectionPointIn><connectionPointOut/>'
            f'<variable>{escape(str(c["args"][0]))}</variable></contact>')


def _in_var(i: int, expression: str) -> str:
    return (f'<inVariable localId="{i}"><position x="0" y="0"/><connectionPointOut/>'
            f'<expression>{escape(expression)}</expression></inVariable>')


def _network(ids: _Ids, rung: dict[str, Any]) -> list[str]:
    parts = [f'<comment localId="{ids.next()}" height="0" width="0"><position x="0" y="0"/>'
             f'<content>{_x(rung.get("comment") or "")}</content></comment>',
             f'<vendorElement localId="{ids.next()}"><position x="0" y="0"/><alternativeText>{_x("")}</alternativeText>'
             f'<addData><data name="{ELEMENT_TYPE}" handleUnknown="implementation">'
             '<ElementType xmlns="">networktitle</ElementType></data></addData></vendorElement>']
    *inputs, output = rung["elements"]

    def series(elements: list[dict[str, Any]], ends: list[tuple[int, str | None]]) -> list[tuple[int, str | None]]:
        for e in elements:
            if "branch" in e:
                leg_ends: list[tuple[int, str | None]] = []
                for leg in e["branch"]:
                    leg_ends += series(leg, ends)
                ends = leg_ends
            else:
                i = ids.next()
                parts.append(_contact(i, e, ends))
                ends = [(i, None)]
        return ends

    ends = series(inputs, [(0, None)])
    kind, args = output["kind"], [str(a) for a in output["args"]]
    if kind in COILS:
        storage = {"OUT": "none", "SET": "set", "RST": "reset"}[kind]
        parts.append(f'<coil localId="{ids.next()}" negated="false" storage="{storage}"><position x="0" y="0"/>'
                     f'<connectionPointIn>{_conn(ends)}</connectionPointIn><connectionPointOut/>'
                     f'<variable>{escape(args[0])}</variable></coil>')
        return parts
    if kind in TIMERS:
        pt = ids.next()
        parts.append(_in_var(pt, args[1]))
        inputs_xml = (f'<variable formalParameter="IN"><connectionPointIn>{_conn(ends)}</connectionPointIn></variable>'
                      f'<variable formalParameter="PT"><connectionPointIn>{_conn([(pt, None)])}</connectionPointIn></variable>')
    else:  # CTU
        rst, pv = ids.next(), ids.next()
        parts += [_in_var(rst, args[2]), _in_var(pv, args[1])]
        inputs_xml = (f'<variable formalParameter="CU"><connectionPointIn>{_conn(ends)}</connectionPointIn></variable>'
                      f'<variable formalParameter="RESET"><connectionPointIn>{_conn([(rst, None)])}</connectionPointIn></variable>'
                      f'<variable formalParameter="PV"><connectionPointIn>{_conn([(pv, None)])}</connectionPointIn></variable>')
    parts.append(f'<block localId="{ids.next()}" typeName="{kind}" instanceName="{escape(args[0])}"><position x="0" y="0"/>'
                 f'<inputVariables>{inputs_xml}</inputVariables><inOutVariables/>'
                 '<outputVariables><variable formalParameter="Q"><connectionPointOut/></variable></outputVariables></block>')
    return parts


def to_plcopen(pou: str, variables: list[dict[str, Any]], rungs: list[dict[str, Any]]) -> str:
    ids = _Ids()
    body = ['<leftPowerRail localId="0"><position x="0" y="0"/><connectionPointOut formalParameter="none"/></leftPowerRail>']
    for rung in rungs:
        body += _network(ids, rung)
    body.append(f'<rightPowerRail localId="{RIGHT_RAIL}"><position x="0" y="0"/><connectionPointIn/></rightPowerRail>')
    return ('<?xml version="1.0" encoding="utf-8"?>'
            f'<project xmlns="{PLCOPEN}">'
            '<fileHeader companyName="" productName="multi-plc-agent" productVersion="codesys_mcp" '
            'creationDateTime="2000-01-01T00:00:00"/>'
            f'<contentHeader name="{escape(pou)}"><coordinateInfo><fbd><scaling x="1" y="1"/></fbd>'
            '<ld><scaling x="1" y="1"/></ld><sfc><scaling x="1" y="1"/></sfc></coordinateInfo></contentHeader>'
            f'<types><dataTypes/><pous><pou name="{escape(pou)}" pouType="program"><interface/>'
            f'<body><LD>{"".join(body)}</LD></body>'
            f'<addData><data name="{PLAINTEXT}" handleUnknown="implementation"><InterfaceAsPlainText>'
            f'{_x(declaration(pou, variables, rungs))}</InterfaceAsPlainText></data></addData>'
            '</pou></pous></types><instances><configurations/></instances></project>')


# --- logic signature -----------------------------------------------------------

def _flat(op: str, items: list[Any]) -> Any:
    out: list[Any] = []
    for it in items:
        if it == "TRUE" and op == "AND":
            continue
        if isinstance(it, tuple) and it[0] == op:
            out += list(it[1:])
        else:
            out.append(it)
    if not out:
        return "TRUE"
    return out[0] if len(out) == 1 else (op, *out)


def _dnf(e: Any) -> frozenset:
    """Sum of products as a set of literal sets; ladder has no negated groups, so this is exact."""
    if isinstance(e, str):
        return frozenset({frozenset({e})}) if e != "TRUE" else frozenset({frozenset()})
    if e[0] == "NOT":
        return frozenset({frozenset({"NOT " + e[1]})})
    if e[0] == "OR":
        return frozenset().union(*(_dnf(x) for x in e[1:]))
    out = frozenset({frozenset()})
    for x in e[1:]:
        out = frozenset(a | b for a in out for b in _dnf(x))
    return out


def _render(e: Any) -> str:
    """Canonical text: OR of AND terms, both sorted, so equal logic gives equal text."""
    terms = sorted(" AND ".join(sorted(t)) or "TRUE" for t in _dnf(e))
    return " OR ".join(f"({t})" if " AND " in t and len(terms) > 1 else t for t in terms)


def _rung_expr(inputs: list[dict[str, Any]]) -> Any:
    terms = []
    for e in inputs:
        if "branch" in e:
            terms.append(_flat("OR", [_rung_expr(leg) for leg in e["branch"]]))
        else:
            terms.append(_contact_expr(e))
    return _flat("AND", terms)


def _contact_expr(c: dict[str, Any]) -> Any:
    name = str(c["args"][0])
    return ("NOT", name) if c["kind"] == "NC" else name


def expected_logic(rungs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for rung in rungs:
        *inputs, output = rung["elements"]
        kind, args = output["kind"], [str(a) for a in output["args"]]
        item = {"comment": rung.get("comment") or "", "kind": kind, "target": args[0], "logic": _render(_rung_expr(inputs))}
        if kind in TIMERS:
            item["params"] = {"PT": args[1]}
        if kind == "CTU":
            item["params"] = {"PV": args[1], "RESET": args[2]}
        out.append(item)
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_logic(xml_text: str, pou: str) -> list[dict[str, Any]]:
    """Logic signature of an LD POU in a PLCopen XML export (CODESYS dialect)."""
    root = ET.fromstring(xml_text.lstrip("\ufeff").encode("utf-8"))
    target = next((p for p in root.iter() if _local(p.tag) == "pou" and p.get("name") == pou), None)
    if target is None:
        raise ValueError(f"POU {pou!r} not found in export")
    ld = next((b for b in target.iter() if _local(b.tag) == "LD"), None)
    if ld is None:
        raise ValueError(f"POU {pou!r} has no LD body")
    nodes: dict[str, ET.Element] = {}
    order: list[ET.Element] = []
    for el in ld:
        if el.get("localId") is not None:
            nodes[el.get("localId")] = el
            order.append(el)

    def refs_of(cp: ET.Element | None) -> list[tuple[str, str | None]]:
        if cp is None:
            return []
        return [(c.get("refLocalId"), c.get("formalParameter")) for c in cp if _local(c.tag) == "connection"]

    def child(el: ET.Element, name: str) -> ET.Element | None:
        return next((c for c in el if _local(c.tag) == name), None)

    def text(el: ET.Element | None) -> str:
        return "".join(el.itertext()).strip() if el is not None else ""

    memo: dict[str, Any] = {}

    def expr(ref: str) -> Any:
        if ref in memo:
            return memo[ref]
        el = nodes[ref]
        kind = _local(el.tag)
        if kind == "leftPowerRail":
            val: Any = "TRUE"
        elif kind == "contact":
            ins = _flat("OR", [expr(r) for r, _ in refs_of(child(el, "connectionPointIn"))])
            name = text(child(el, "variable"))
            val = _flat("AND", [ins, ("NOT", name) if el.get("negated") == "true" else name])
        elif kind == "inVariable":
            val = text(child(el, "expression"))
        else:
            raise ValueError(f"unsupported element {kind} as a contact input")
        memo[ref] = val
        return val

    def block_inputs(el: ET.Element) -> dict[str, list[tuple[str, str | None]]]:
        found = {}
        for v in child(el, "inputVariables") or []:
            found[v.get("formalParameter")] = refs_of(child(v, "connectionPointIn"))
        return found

    networks: list[dict[str, Any]] = []
    comment = ""
    for el in order:
        kind = _local(el.tag)
        if kind == "comment":
            comment = text(child(el, "content"))
        elif kind == "coil":
            storage = el.get("storage") or "none"
            networks.append({"comment": comment, "kind": {"none": "OUT", "set": "SET", "reset": "RST"}[storage],
                             "target": text(child(el, "variable")),
                             "logic": _render(_flat("OR", [expr(r) for r, _ in refs_of(child(el, "connectionPointIn"))]))})
        elif kind == "block":
            ins = block_inputs(el)
            btype = el.get("typeName")
            first = "IN" if btype in TIMERS else "CU"
            item = {"comment": comment, "kind": btype, "target": el.get("instanceName"),
                    "logic": _render(_flat("OR", [expr(r) for r, _ in ins.get(first, [])]))}
            consts = {k: _render(_flat("OR", [expr(r) for r, _ in v])) for k, v in ins.items() if k != first}
            item["params"] = consts
            networks.append(item)
    return networks
