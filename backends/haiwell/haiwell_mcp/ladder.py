"""Rung model for Haiwell Happy: validation, keystroke plan and expected IL.

Haiwell Happy has no text import for ladder, so rungs are typed into the LD
editor with its documented shortcuts (HaiwellHappy_en.chm, "Programming"):
Ctrl+L add network, F9 series contact, F10 parallel contact, F11 output coil,
Ctrl+2 normally closed, Enter edits the operand, "ADDR//text" sets a component
comment, typing the first letter of an instruction opens its input box.
The result is checked by exporting IL (Tools > Convert program to IL) and
comparing it with `expected_il`.

Rung JSON:
    {"comment": "Run request",
     "elements": [
        {"branch": [[{"kind": "NO", "args": ["X0"], "note": "Start"}],
                    [{"kind": "NO", "args": ["M0"]}]]},
        {"kind": "NC", "args": ["X1"], "note": "Stop"},
        {"kind": "OUT", "args": ["M0"], "note": "Run request"}]}

Limits of the keystroke path (validated): one output per rung, at the end;
a branch's first leg is a single contact on the main line, other legs are one
or more contacts; branches are not nested.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CONTACTS = ("NO", "NC")
# kind -> argument names; IL rendering in _output_il
OUTPUTS = {
    "OUT": ("coil",),
    "SET": ("bit",),
    "RST": ("target",),
    "TON": ("timer", "preset_s"),
    "CTU": ("counter", "preset"),
}
BIT = re.compile(r"^(X|Y|M|S|T|C|SM)\d+$")
TIMER = re.compile(r"^T(\d+)$")
COUNTER = re.compile(r"^C(\d+)$")
SENDKEYS_SPECIAL = set("+^%~(){}[]")


@dataclass
class Finding:
    level: str
    rung: int | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"level": self.level, "rung": self.rung, "message": self.message}


def _is_contact(e: Any) -> bool:
    return isinstance(e, dict) and e.get("kind") in CONTACTS


def _text_ok(text: str) -> bool:
    return "\n" not in text and "\r" not in text and "//" not in text


def validate(rungs: list[dict[str, Any]], aliases: dict[str, str] | None = None) -> list[Finding]:
    out: list[Finding] = []

    def err(i: int | None, msg: str) -> None:
        out.append(Finding("error", i, msg))

    def check_contact(i: int, c: Any, where: str) -> None:
        if not _is_contact(c):
            err(i, f"{where}: expected a contact {{kind: NO|NC, args: [address]}}, got {c!r}")
            return
        args = c.get("args") or []
        if len(args) != 1 or not BIT.match(str(args[0])):
            err(i, f"{where}: contact needs one bit address like X0, Y1, M5, T0, C0 (got {args!r})")
        if not _text_ok(str(c.get("note", ""))):
            err(i, f"{where}: note must be one line without '//'")

    if not rungs:
        err(None, "no rungs")
    for i, rung in enumerate(rungs):
        if not isinstance(rung, dict) or not isinstance(rung.get("elements"), list):
            err(i, "rung must be {comment?, elements: [...]}")
            continue
        if not _text_ok(str(rung.get("comment", ""))):
            err(i, "rung comment must be one line without '//'")
        elems = rung["elements"]
        if len(elems) < 2:
            err(i, "a rung needs at least one contact and one output")
            continue
        *inputs, output = elems
        for j, e in enumerate(inputs):
            if isinstance(e, dict) and "branch" in e:
                legs = e["branch"]
                if not isinstance(legs, list) or len(legs) < 2:
                    err(i, f"element {j}: a branch needs at least two legs")
                    continue
                if not isinstance(legs[0], list) or len(legs[0]) != 1:
                    err(i, f"element {j}: the first leg of a branch must be exactly one contact "
                           "(put longer paths in the later legs)")
                for k, leg in enumerate(legs):
                    if not isinstance(leg, list) or not leg:
                        err(i, f"element {j} leg {k}: empty leg")
                        continue
                    for c in leg:
                        check_contact(i, c, f"element {j} leg {k}")
            else:
                check_contact(i, e, f"element {j}")
        kind = output.get("kind") if isinstance(output, dict) else None
        if kind not in OUTPUTS:
            err(i, f"last element must be one of {sorted(OUTPUTS)} (got {kind!r}); "
                   "one output per rung")
            continue
        args = [str(a) for a in output.get("args") or []]
        if len(args) != len(OUTPUTS[kind]):
            err(i, f"{kind} takes {len(OUTPUTS[kind])} args {list(OUTPUTS[kind])}, got {args!r}")
            continue
        if kind in ("OUT", "SET") and (not BIT.match(args[0]) or args[0].startswith("X")):
            err(i, f"{kind} target must be a writable bit (Y, M, S, ...), got {args[0]!r}")
        if kind == "RST" and not BIT.match(args[0]):
            err(i, f"RST target must be a bit, timer or counter, got {args[0]!r}")
        if kind == "TON" and not TIMER.match(args[0]):
            err(i, f"TON needs a timer like T0, got {args[0]!r}")
        if kind == "CTU" and not COUNTER.match(args[0]):
            err(i, f"CTU needs a counter like C0, got {args[0]!r}")
        if kind in ("TON", "CTU") and not (args[1].isdigit() and 0 < int(args[1]) <= 32767):
            err(i, f"{kind} preset must be an integer 1..32767, got {args[1]!r}")
        if not _text_ok(str(output.get("note", ""))):
            err(i, "output note must be one line without '//'")
    for addr, text in (aliases or {}).items():
        if not BIT.match(addr) or not _text_ok(text):
            err(None, f"alias {addr!r}: address must be a bit address and text one line without '//'")
    return out


def _escape(text: str) -> str:
    return "".join("{%s}" % ch if ch in SENDKEYS_SPECIAL else ch for ch in text)


class _Comments:
    """Attach each address comment once, at the first operand that uses it."""

    def __init__(self, aliases: dict[str, str]):
        self.pending = dict(aliases)

    def operand(self, addr: str, note: str | None) -> str:
        text = note or self.pending.get(addr)
        self.pending.pop(addr, None)
        return _escape(f"{addr}//{text}" if text else addr)


def _contact_keys(c: dict[str, Any], insert_key: str, comments: _Comments) -> list[str]:
    keys = [insert_key]
    if c["kind"] == "NC":
        keys.append("^2")
    keys += ["{ENTER}", comments.operand(str(c["args"][0]), c.get("note")) + "{ENTER}"]
    return keys


def _output_keys(o: dict[str, Any], comments: _Comments) -> list[str]:
    kind, args = o["kind"], [str(a) for a in o["args"]]
    if kind == "OUT":
        return ["{F11}", "{ENTER}", comments.operand(args[0], o.get("note")) + "{ENTER}"]
    # instruction input box: first letter opens it, the rest + Enter inserts
    keys = ["{RIGHT}", kind[0], kind[1:] + "{ENTER}", "{ENTER}"]
    if kind in ("SET", "RST"):
        return keys + [comments.operand(args[0], o.get("note")) + "{ENTER}"]
    target, preset = args
    return keys + [preset + "{ENTER}", comments.operand(target, o.get("note")) + "{ENTER}"]


def plan(rungs: list[dict[str, Any]], aliases: dict[str, str] | None = None) -> dict[str, Any]:
    """Keystroke steps for the GUI driver: {"k": keys} or {"comment": text}."""
    comments = _Comments(aliases or {})
    steps: list[dict[str, Any]] = [{"k": "^a"}, {"k": "{DEL}"}]
    for i, rung in enumerate(rungs):
        steps.append({"k": "^l", "rung": i})
        if rung.get("comment"):
            steps.append({"comment": rung["comment"]})
        *inputs, output = rung["elements"]
        tops = [e["branch"][0][0] if "branch" in e else e for e in inputs]
        for c in tops:
            steps += [{"k": k} for k in _contact_keys(c, "{F9}", comments)]
        # Main-line contacts sit in adjacent grid cells, so LEFT/RIGHT step one
        # contact at a time; the cells before the output are empty wire whose
        # count depends on the rung width. Add branches while the cursor is
        # still on the contacts, walk back to the last contact, then the output.
        last = len(tops) - 1
        cursor = last
        for j in range(last, -1, -1):
            if "branch" not in inputs[j]:
                continue
            steps += [{"k": "{LEFT}"}] * (cursor - j)
            cursor = j
            # F10 inserts directly under the main contact, so add legs bottom-up
            for leg in reversed(inputs[j]["branch"][1:]):
                steps += [{"k": k} for k in _contact_keys(leg[0], "{F10}", comments)]
                for c in leg[1:]:
                    steps += [{"k": k} for k in _contact_keys(c, "{F9}", comments)]
                steps += [{"k": "{LEFT}"}] * (len(leg) - 1) + [{"k": "{UP}"}]
        # a leg of n contacts widens its branch to n grid cells, and the main
        # line gets empty cells over the extra ones, each one more RIGHT press
        steps += [{"k": "{RIGHT}"}] * sum(
            max(len(leg) for leg in inputs[p]["branch"]) if "branch" in inputs[p] else 1
            for p in range(cursor, last))
        steps += [{"k": k} for k in _output_keys(output, comments)]
    return {"steps": steps, "unapplied_aliases": comments.pending}


def _contact_il(c: dict[str, Any], op: str) -> tuple[str, list[str]]:
    return (op + ("I" if c["kind"] == "NC" else ""), [str(c["args"][0])])


def _output_il(o: dict[str, Any]) -> tuple[str, list[str]]:
    kind, args = o["kind"], [str(a) for a in o["args"]]
    if kind == "TON":
        return ("TON.1s", [args[1], args[0], "TV" + args[0][1:]])
    if kind == "CTU":
        return ("CTU", [args[1], args[0], "CV" + args[0][1:]])
    return (kind, args)


def expected_il(rungs: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    il: list[tuple[str, list[str]]] = []
    for rung in rungs:
        *inputs, output = rung["elements"]
        for pos, e in enumerate(inputs):
            if "branch" not in e:
                il.append(_contact_il(e, "LD" if pos == 0 else "AND"))
                continue
            legs = e["branch"]
            il.append(_contact_il(legs[0][0], "LD"))
            for leg in legs[1:]:
                if len(leg) == 1:
                    il.append(_contact_il(leg[0], "OR"))
                else:
                    il.append(_contact_il(leg[0], "LD"))
                    il += [_contact_il(c, "AND") for c in leg[1:]]
                    il.append(("ORB", []))
            if pos > 0:
                il.append(("ANDB", []))
        il.append(_output_il(output))
    return il


def parse_il(text: str, block: str = "MainLD") -> list[tuple[str, list[str]]]:
    """Instructions of one program block from a Convert-program-to-IL export."""
    out: list[tuple[str, list[str]]] = []
    inside = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("Main program:") or line.startswith("Sub program:") or line.startswith("Int program:"):
            inside = f"[PGB:{block}]" in line
            continue
        if not inside or not line or line == "END":
            continue
        mnemonic, _, rest = line.partition(" ")
        ops = [p.strip() for p in rest.split(",")] if rest.strip() else []
        out.append((mnemonic, ops))
    return out


def il_text(il: list[tuple[str, list[str]]]) -> list[str]:
    return [f"{m:<11} {', '.join(ops)}".rstrip() for m, ops in il]
