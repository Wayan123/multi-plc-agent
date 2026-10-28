"""Rung model, validation, IL generation and the DVP instruction-word codec.

WPLSoft keeps a DVP-ES2/SS2 program as a stream of 16-bit words (the same
words it puts on the clipboard as CF_INST). Encodings below were taken from
WPLSoft 2.52 by entering each instruction in Instruction List mode and
reading the words back (Edit > Copy and saved .dvp files):

    device address  S n = n, X n = 0x400+n, Y n = 0x500+n, T n = 0x600+n,
                    M n = 0x800+n (n < 1536) or 0xA00+n (n >= 1536),
                    C n = 0xE00+n            (X/Y numbers are octal)
    LD/LDI/AND/ANI/OR/ORI/OUT/SET on an address below 0x1000:
                    one word (op << 8) | address, op = 0x20 0x30 0x40 0x50
                    0x60 0x70 0xC0 0xD0 (the address high nibble is or-ed in)
    same on M1536..M4095: 0x0202..0x0207 / 0x020C / 0x020D + operand pair
    operand pair    bit device: 0x8400|lo, 0x8000|hi
                    T (RST):    0x8600|n,  0x8206
                    C (RST):    0x8600|n,  0x840E
    RST d           0x0007 + operand pair
    TMR Tn Kv       0x0003, 0x8100|n, 0x8000|lo(v), 0x8000|hi(v)
    CNT Cn Kv       0x0005, 0x8300|n, 0x8000|lo(v), 0x8000|hi(v)
    ANB 0xFFF8  ORB 0xFFF9  MPS 0xFFFA  MRD 0xFFFB  MPP 0xFFFC  END 0x000F
    unused program memory 0xFFFF

Rung JSON (one output, last):
    {"comment": "Run request",
     "elements": [
        {"branch": [[{"kind": "NO", "args": ["X0"]}], [{"kind": "NO", "args": ["M0"]}]]},
        {"kind": "NC", "args": ["X1"], "note": "Stop PB"},
        {"kind": "OUT", "args": ["M0"]}]}
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

CONTACTS = {"NO": ("LD", "AND", "OR"), "NC": ("LDI", "ANI", "ORI")}
OUTPUTS = {"OUT": 1, "SET": 1, "RST": 1, "TMR": 2, "CNT": 2}

# Device ranges of DVP-ES2/SS2 (WPLSoft DeviceRange.ini, [ES2_*] and [SS2_*]).
RANGES = {"X": 0o377, "Y": 0o377, "M": 4095, "S": 1023, "T": 255, "C": 255}
CNT16_LAST = 199  # C200.. are 32-bit counters (DCNT), not supported here
COMMENT_MAX = 60  # WPLSoft manual 6.3: segment comments hold 60 characters

ADDRESS = re.compile(r"^([XYMSTC])(\d+)$")
PRESET = re.compile(r"^K(\d+)$")

BASIC = {"LD": 0x20, "LDI": 0x30, "AND": 0x40, "ANI": 0x50, "OR": 0x60, "ORI": 0x70,
         "OUT": 0xC0, "SET": 0xD0}
EXTENDED = {"LD": 0x0202, "LDI": 0x0203, "AND": 0x0204, "ANI": 0x0205, "OR": 0x0206,
            "ORI": 0x0207, "OUT": 0x020C, "SET": 0x020D}
NOARG = {"ANB": 0xFFF8, "ORB": 0xFFF9, "MPS": 0xFFFA, "MRD": 0xFFFB, "MPP": 0xFFFC, "END": 0x000F}
OP_RST, OP_TMR, OP_CNT, EMPTY = 0x0007, 0x0003, 0x0005, 0xFFFF

Instr = tuple[str, tuple[str, ...]]


@dataclass
class Finding:
    level: str
    rung: int | None
    message: str

    def to_json(self) -> dict[str, Any]:
        return {"level": self.level, "rung": self.rung, "message": self.message}


# -- devices ------------------------------------------------------------------
def parse_address(addr: str) -> tuple[str, int]:
    m = ADDRESS.match(addr)
    if not m:
        raise ValueError(f"{addr!r} is not a DVP bit address (X0, Y0, M0, S0, T0, C0)")
    kind, digits = m.group(1), m.group(2)
    if kind in "XY":
        if set(digits) - set("01234567"):
            raise ValueError(f"{addr}: X and Y are numbered in octal (X0..X7, X10..)")
        number = int(digits, 8)
    else:
        number = int(digits)
    if number > RANGES[kind]:
        last = f"{RANGES[kind]:o}" if kind in "XY" else str(RANGES[kind])
        raise ValueError(f"{addr}: out of range for ES2/SS2 ({kind}0..{kind}{last})")
    return kind, number


def device_address(kind: str, number: int) -> int:
    if kind == "M":
        return 0x800 + number if number < 1536 else 0xA00 + number
    return {"S": 0, "X": 0x400, "Y": 0x500, "T": 0x600, "C": 0xE00}[kind] + number


def address_name(address: int) -> str:
    if address < 0x400:
        return f"S{address}"
    if address < 0x500:
        return f"X{address - 0x400:o}"
    if address < 0x600:
        return f"Y{address - 0x500:o}"
    if address < 0x700:
        return f"T{address - 0x600}"
    if 0x800 <= address < 0xE00:
        return f"M{address - 0x800}"
    if 0xE00 <= address < 0xF00:
        return f"C{address - 0xE00}"
    if 0x1000 <= address <= 0xA00 + 4095:
        return f"M{address - 0xA00}"
    raise ValueError(f"unknown device address 0x{address:04X}")


# -- validation -----------------------------------------------------------------
def _text_ok(text: str) -> bool:
    return all(32 <= ord(ch) < 127 for ch in text) and "$&" not in text and len(text) <= COMMENT_MAX


def validate(rungs: list[dict[str, Any]], aliases: dict[str, str] | None = None) -> list[Finding]:
    out: list[Finding] = []

    def err(i: int | None, msg: str) -> None:
        out.append(Finding("error", i, msg))

    def check_address(i: int, addr: Any, where: str) -> tuple[str, int] | None:
        try:
            return parse_address(str(addr))
        except ValueError as e:
            err(i, f"{where}: {e}")
            return None

    def check_note(i: int, e: dict, where: str) -> None:
        if "note" in e and not _text_ok(str(e["note"])):
            err(i, f"{where}: note must be printable ASCII, at most {COMMENT_MAX} chars, without '$&'")

    def check_series(i: int, series: Any, where: str) -> None:
        if not isinstance(series, list) or not series:
            err(i, f"{where}: expected a non-empty list of contacts/branches")
            return
        for j, e in enumerate(series):
            here = f"{where} element {j}"
            if isinstance(e, dict) and "branch" in e:
                legs = e["branch"]
                if not isinstance(legs, list) or len(legs) < 2:
                    err(i, f"{here}: a branch needs at least two legs")
                    continue
                for k, leg in enumerate(legs):
                    check_series(i, leg, f"{here} leg {k}")
            elif isinstance(e, dict) and e.get("kind") in CONTACTS:
                args = e.get("args") or []
                if len(args) != 1:
                    err(i, f"{here}: a contact takes one address")
                else:
                    check_address(i, args[0], here)
                check_note(i, e, here)
            else:
                err(i, f"{here}: expected a contact {{kind: NO|NC, args: [addr]}} or {{branch: [...]}}, got {e!r}")

    if not rungs:
        err(None, "no rungs")
    for i, rung in enumerate(rungs):
        if not isinstance(rung, dict) or not isinstance(rung.get("elements"), list):
            err(i, "rung must be {comment?, elements: [...]}")
            continue
        if rung.get("comment") is not None and not _text_ok(str(rung["comment"])):
            err(i, f"rung comment must be printable ASCII, at most {COMMENT_MAX} chars")
        elems = rung["elements"]
        if len(elems) < 2:
            err(i, "a rung needs at least one contact and one output")
            continue
        *inputs, output = elems
        check_series(i, inputs, "inputs")
        kind = output.get("kind") if isinstance(output, dict) else None
        if kind not in OUTPUTS:
            err(i, f"last element must be one of {sorted(OUTPUTS)} (got {kind!r}); one output per rung")
            continue
        args = [str(a) for a in output.get("args") or []]
        if len(args) != OUTPUTS[kind]:
            err(i, f"{kind} takes {OUTPUTS[kind]} argument(s), got {args!r}")
            continue
        check_note(i, output, "output")
        dev = check_address(i, args[0], kind)
        if dev is None:
            continue
        if kind in ("OUT", "SET") and dev[0] not in "YMS":
            err(i, f"{kind} target must be Y, M or S (timers use TMR, counters CNT), got {args[0]}")
        if kind == "RST" and dev[0] == "X":
            err(i, f"RST cannot target an input, got {args[0]}")
        if kind == "RST" and dev[0] == "C" and dev[1] > CNT16_LAST:
            err(i, f"only 16-bit counters C0..C{CNT16_LAST} are supported, got {args[0]}")
        if kind in ("TMR", "CNT"):
            want = "T" if kind == "TMR" else "C"
            if dev[0] != want:
                err(i, f"{kind} needs a {want} device, got {args[0]}")
            if kind == "CNT" and dev[1] > CNT16_LAST:
                err(i, f"CNT supports 16-bit counters C0..C{CNT16_LAST}, got {args[0]}")
            m = PRESET.match(args[1])
            if not m or not 1 <= int(m.group(1)) <= 32767:
                err(i, f"{kind} preset must be K1..K32767, got {args[1]!r}")
    for addr, text in (aliases or {}).items():
        try:
            parse_address(addr)
        except ValueError as e:
            err(None, f"alias {addr!r}: {e}")
        if not _text_ok(str(text)):
            err(None, f"alias {addr!r}: text must be printable ASCII, at most {COMMENT_MAX} chars, without '$&'")
    return out


# -- rung -> IL -------------------------------------------------------------------
def _canon(addr: str) -> str:
    kind, number = parse_address(addr)
    return f"{kind}{number:o}" if kind in "XY" else f"{kind}{number}"


def _contact(e: dict[str, Any], form: int) -> Instr:
    return (CONTACTS[e["kind"]][form], (_canon(str(e["args"][0])),))


def _series(series: list[Any]) -> list[Instr]:
    """IL of a series whose first element starts a new logic block (LD form)."""
    out: list[Instr] = []
    for pos, e in enumerate(series):
        if "branch" in e:
            out += _branch(e["branch"])
            if pos:
                out.append(("ANB", ()))
        else:
            out.append(_contact(e, 0 if pos == 0 else 1))
    return out


def _branch(legs: list[list[Any]]) -> list[Instr]:
    out = _series(legs[0])
    for leg in legs[1:]:
        if len(leg) == 1 and "branch" not in leg[0]:
            out.append(_contact(leg[0], 2))
        else:
            out += _series(leg) + [("ORB", ())]
    return out


def _output(o: dict[str, Any]) -> Instr:
    kind, args = o["kind"], [str(a) for a in o["args"]]
    if kind in ("TMR", "CNT"):
        return (kind, (_canon(args[0]), f"K{int(args[1][1:])}"))
    return (kind, (_canon(args[0]),))


def rung_il(rung: dict[str, Any]) -> list[Instr]:
    *inputs, output = rung["elements"]
    return _series(inputs) + [_output(output)]


def expected_il(rungs: list[dict[str, Any]]) -> list[Instr]:
    il = [ins for rung in rungs for ins in rung_il(rung)]
    return il + [("END", ())]


def il_text(il: list[Instr]) -> list[str]:
    return [" ".join((m, *ops)) for m, ops in il]


def parse_il_line(line: str) -> Instr:
    mnemonic, *ops = line.split()
    return (mnemonic.upper(), tuple(o.upper() for o in ops))


# -- IL <-> words -------------------------------------------------------------------
def _pair(address: int) -> list[int]:
    return [0x8400 | (address & 0xFF), 0x8000 | (address >> 8)]


def encode(il: list[Instr]) -> list[int]:
    words: list[int] = []
    for mnemonic, ops in il:
        if mnemonic in NOARG:
            words.append(NOARG[mnemonic])
            continue
        kind, number = parse_address(ops[0])
        address = device_address(kind, number)
        if mnemonic in BASIC:
            if address < 0x1000:
                words.append(((BASIC[mnemonic] | (address >> 8)) << 8) | (address & 0xFF))
            else:
                words += [EXTENDED[mnemonic], *_pair(address)]
        elif mnemonic == "RST":
            if kind == "T":
                words += [OP_RST, 0x8600 | number, 0x8206]
            elif kind == "C":
                words += [OP_RST, 0x8600 | number, 0x840E]
            else:
                words += [OP_RST, *_pair(address)]
        elif mnemonic in ("TMR", "CNT"):
            value = int(ops[1][1:])
            words += [OP_TMR if mnemonic == "TMR" else OP_CNT,
                      (0x8100 if mnemonic == "TMR" else 0x8300) | number,
                      0x8000 | (value & 0xFF), 0x8000 | (value >> 8)]
        else:
            raise ValueError(f"cannot encode {mnemonic}")
    return words


_BASIC_BY_OP = {v: k for k, v in BASIC.items()}
_EXT_BY_OP = {v: k for k, v in EXTENDED.items()}
_NOARG_BY_WORD = {v: k for k, v in NOARG.items()}


def decode(words: list[int]) -> list[Instr]:
    """Words up to the first 0xFFFF; unknown words become ("?", ("0xNNNN",))."""
    out: list[Instr] = []
    i = 0

    def pair(at: int) -> int:
        lo, hi = words[at], words[at + 1]
        if lo & 0xFF00 != 0x8400 or hi & 0xFF00 != 0x8000:
            raise ValueError
        return (lo & 0xFF) | ((hi & 0xFF) << 8)

    while i < len(words) and words[i] != EMPTY:
        w = words[i]
        try:
            if w in _NOARG_BY_WORD:
                out.append((_NOARG_BY_WORD[w], ()))
                i += 1
            elif w in _EXT_BY_OP:
                out.append((_EXT_BY_OP[w], (address_name(pair(i + 1)),)))
                i += 3
            elif w == OP_RST:
                lo, hi = words[i + 1], words[i + 2]
                if lo & 0xFF00 == 0x8600 and hi == 0x8206:
                    out.append(("RST", (f"T{lo & 0xFF}",)))
                elif lo & 0xFF00 == 0x8600 and hi == 0x840E:
                    out.append(("RST", (f"C{lo & 0xFF}",)))
                else:
                    out.append(("RST", (address_name(pair(i + 1)),)))
                i += 3
            elif w in (OP_TMR, OP_CNT):
                dev, lo, hi = words[i + 1], words[i + 2], words[i + 3]
                prefix, tag = ("T", 0x8100) if w == OP_TMR else ("C", 0x8300)
                if dev & 0xFF00 != tag or lo & 0xFF00 != 0x8000 or hi & 0xFF00 != 0x8000:
                    raise ValueError
                value = (lo & 0xFF) | ((hi & 0xFF) << 8)
                out.append(("TMR" if w == OP_TMR else "CNT", (f"{prefix}{dev & 0xFF}", f"K{value}")))
                i += 4
            elif (w >> 8) & 0xF0 in _BASIC_BY_OP and w >> 12 >= 2:
                op = (w >> 8) & 0xF0
                out.append((_BASIC_BY_OP[op], (address_name(((w >> 8) & 0x0F) << 8 | (w & 0xFF)),)))
                i += 1
            else:
                raise ValueError
        except (ValueError, IndexError):
            out.append(("?", (f"0x{w:04X}",)))
            i += 1
    return out


def device_notes(rungs: list[dict[str, Any]], aliases: dict[str, str] | None) -> dict[str, str]:
    """Device comment per canonical address: aliases first, element notes override."""
    notes = {_canon(a): str(t) for a, t in (aliases or {}).items()}

    def walk(series: list[Any]) -> None:
        for e in series:
            if "branch" in e:
                for leg in e["branch"]:
                    walk(leg)
            elif e.get("note"):
                notes[_canon(str(e["args"][0]))] = str(e["note"])

    for rung in rungs:
        *inputs, output = rung["elements"]
        walk(inputs + [output])
    return notes
