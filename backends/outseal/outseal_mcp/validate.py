"""Static checks for Outseal ladder before it reaches Outseal Studio.

Outseal Studio's own Test does not reject out-of-range I/O (for example
R.99 on a Nano), so this module checks addresses against each board's
documented I/O counts, plus instruction names and argument counts.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .codec import Element, Project, Rung

# Board name as written in the project file -> (digital inputs, digital outputs, analog inputs).
# Sources: outseal.com product pages (Nano V5.2: 8/8/2; Mega V2 Full and V3 Standard: 16/16/2).
BOARDS: dict[str, tuple[int, int, int]] = {
    "Nano V5": (8, 8, 2),
    "Mega V1/Compact": (16, 16, 2),
    "Mega V2/Compact": (16, 16, 2),
    "Mega V3": (16, 16, 2),
    "Mega Slim V1": (16, 16, 2),
}

# Instruction -> argument count, from the instruction reference and bundled examples.
ARITY: dict[str, int] = {
    "NO": 1, "NC": 1, "OUT": 1, "OUTN": 1, "OUTL": 1, "OUTU": 1, "FOR": 1, "FOF": 1,
    "OSR": 1, "OSF": 1, "RST": 1,
    "TON": 3, "TOF": 3, "RTO": 3, "CTU": 3, "CTD": 3,
    "EQU": 2, "NEQ": 2, "GEQ": 2, "GRT": 2, "LEQ": 2, "LES": 2,
    "LIM": 3, "ADD": 3, "SUB": 3, "MUL": 3, "DIV": 3, "NEG": 2, "SET": 2, "SPWM": 4,
}
OUTPUT_KINDS = {"OUT", "OUTN", "OUTL", "OUTU", "TON", "TOF", "RTO", "CTU", "CTD", "RST", "ADD", "SUB",
                "MUL", "DIV", "NEG", "SET", "SPWM", "FOR", "FOF"}
BIT_KINDS = {"NO", "NC", "OUT", "OUTN", "OUTL", "OUTU", "FOR", "FOF"}

SUFFIXES = {"T": {"EN", "TT", "DN"}, "C": {"CU", "CD", "DN", "OV", "UN"}, "P": {"EN", "ST", "ON", "OFF"}}
WORD_SUFFIXES = {"T": {"PRE", "ACC"}, "C": {"PRE", "ACC"}}
ADDRESS = re.compile(r"^(S|R|B|I|L|T|C|P|A)\.(\d+)(?:\.([A-Z]+))?$")


@dataclass
class Finding:
    level: str  # "error" or "warning"
    where: str
    message: str

    def to_json(self) -> dict:
        return {"level": self.level, "where": self.where, "message": self.message}


def _check_address(addr: str, board: tuple[int, int, int] | None, where: str, *, bit: bool) -> list[Finding]:
    m = ADDRESS.match(addr)
    if not m:
        return [Finding("error", where, f"{addr!r} is not an Outseal address (examples: S.1, R.1, B.1, T.1.DN, C.1.DN)")]
    area, index, suffix = m.group(1), int(m.group(2)), m.group(3)
    out: list[Finding] = []
    if index < 1:
        out.append(Finding("error", where, f"{addr}: Outseal addresses start at 1"))
    if board:
        limits = {"S": board[0], "R": board[1], "A": board[2]}
        if area in limits and index > limits[area]:
            out.append(Finding("error", where, f"{addr}: this board has {area}.1 to {area}.{limits[area]}"))
    if suffix:
        allowed = SUFFIXES.get(area, set()) | WORD_SUFFIXES.get(area, set())
        if suffix not in allowed:
            out.append(Finding("error", where, f"{addr}: {area} has no .{suffix} member"))
    if bit and area in ("I", "L", "A"):
        out.append(Finding("error", where, f"{addr} is a word register, not a bit"))
    if bit and area in ("T", "C", "P") and suffix not in SUFFIXES.get(area, set()):
        out.append(Finding("error", where, f"{addr}: use a status bit such as {area}.{index}.DN"))
    return out


def _is_number(text: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", text))


def _check_element(e: Element, board, where: str) -> list[Finding]:
    if e.kind == "Branch":
        out = []
        if not e.legs or len(e.legs) < 2:
            out.append(Finding("error", where, "a branch needs at least two legs"))
        for li, leg in enumerate(e.legs or []):
            if not leg:
                out.append(Finding("error", f"{where} leg {li}", "empty branch leg"))
            for ei, x in enumerate(leg):
                out += _check_element(x, board, f"{where} leg {li} element {ei}")
        return out
    if e.kind not in ARITY:
        return [Finding("error", where, f"unknown instruction {e.kind!r}; known: {', '.join(sorted(ARITY))}")]
    if len(e.args) != ARITY[e.kind]:
        return [Finding("error", where, f"{e.kind} takes {ARITY[e.kind]} argument(s), got {len(e.args)}")]
    out: list[Finding] = []
    if e.kind in BIT_KINDS:
        out += _check_address(e.args[0], board, where, bit=True)
        if e.kind != "NO" and e.kind != "NC" and e.args[0].startswith("S."):
            out.append(Finding("error", where, f"{e.args[0]} is an input and cannot be written"))
    elif e.kind in ("TON", "TOF", "RTO"):
        if not re.fullmatch(r"T\.\d+", e.args[0]):
            out.append(Finding("error", where, f"{e.kind} needs a timer such as T.1, got {e.args[0]!r}"))
        if e.args[1] not in ("1000", "100", "10", "1"):
            out.append(Finding("error", where, f"{e.kind} time base must be 1000, 100, 10 or 1 ms, got {e.args[1]!r}"))
        if not _is_number(e.args[2]) or int(e.args[2]) < 0:
            out.append(Finding("error", where, f"{e.kind} preset must be a non-negative integer, got {e.args[2]!r}"))
    elif e.kind in ("CTU", "CTD"):
        if not re.fullmatch(r"C\.\d+", e.args[0]):
            out.append(Finding("error", where, f"{e.kind} needs a counter such as C.1, got {e.args[0]!r}"))
        if not _is_number(e.args[1]):
            out.append(Finding("error", where, f"{e.kind} preset must be an integer, got {e.args[1]!r}"))
    elif e.kind == "RST":
        if not re.fullmatch(r"[TCP]\.\d+", e.args[0]):
            out.append(Finding("error", where, f"RST needs T.n, C.n or P.n, got {e.args[0]!r}"))
    elif e.kind in ("OSR", "OSF"):
        if e.args != [""]:
            out.append(Finding("error", where, f"{e.kind} takes no operand"))
    return out


def _check_rung(r: Rung, board, where: str) -> list[Finding]:
    out: list[Finding] = []
    for i, e in enumerate(r.elements):
        out += _check_element(e, board, f"{where} element {i}")
    if r.elements:
        last = r.elements[-1]
        ends_in_output = (last.kind in OUTPUT_KINDS if last.kind != "Branch"
                          else all(leg and leg[-1].kind in OUTPUT_KINDS for leg in last.legs or []))
        if not ends_in_output:
            out.append(Finding("error", where, "a rung must end with an output instruction (OUT, TON, CTU, RST, ...) "
                                               "or a branch whose legs each end with one"))
        for e in r.elements[:-1]:
            if e.kind in ("TON", "TOF", "RTO", "CTU", "CTD", "SPWM"):
                out.append(Finding("error", where, f"{e.kind} must be the last element of its rung"))
    return out


def validate(project: Project) -> list[Finding]:
    board = BOARDS.get(project.hardware)
    out: list[Finding] = []
    if board is None:
        out.append(Finding("warning", "project", f"unknown board {project.hardware!r}; I/O ranges not checked. "
                                                f"Known: {', '.join(BOARDS)}"))
    for name, rungs in (("Initial", project.initial), ("Main", project.main)):
        for i, r in enumerate(rungs):
            out += _check_rung(r, board, f"{name} rung {i}")
    writers: dict[str, list[str]] = {}
    for i, r in enumerate(project.main):
        for e in r.elements:
            if e.kind == "OUT":
                writers.setdefault(e.args[0], []).append(f"Main rung {i}")
    for addr, places in writers.items():
        if len(places) > 1:
            out.append(Finding("warning", ", ".join(places), f"{addr} is driven by OUT in several rungs; the last one wins"))
    for addr in project.aliases:
        if not ADDRESS.match(addr):
            out.append(Finding("error", "aliases", f"alias key {addr!r} is not an Outseal address"))
    return out
