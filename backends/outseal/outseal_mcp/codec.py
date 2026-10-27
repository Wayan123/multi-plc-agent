"""Outseal Studio .plc codec.

The file is a fixed ASCII banner followed by a gzip stream of UTF-16LE text.
Unicode symbols in the U+24xx and U+26xx ranges delimit the project header,
diagrams (Initial, Main), rungs, elements, parallel branches, notes, rung
comments, a settings block and the alias (symbol) table.

The format is not published by Outseal. It was decoded from files saved by
Outseal Studio V3.6 and from its bundled examples. Writing then reopening a
file in Outseal Studio reproduces the same text.
"""
from __future__ import annotations

import gzip
import io
from dataclasses import dataclass, field
from pathlib import Path

BANNER = (b"OUTSEAL PLC STUDIO, www.outseal.com, mengubah arduino menjadi PLC professional, "
          b"turn your arduino into a professional PLC ")

D_VER, D_HDR, D_HDR_END, STAR = "\u269E", "\u26A0", "\u269F", "\u2605"
D_INIT, D_MAIN, D_DIAG_END = "\u2690", "\u2692", "\u2691"
DIAG, SEP, DIAG_END = "\u24B9", "\u249F", "\u24D3"
RUNG, RUNG_END, CMT = "\u24C9", "\u24E3", "\u24DB"
EL, EL_ARGS, ARG, EL_END = "\u24C0", "\u24C8", "\u24E2", "\u24DA"
BR, BR_END = "\u24B8", "\u24D2"
SETTINGS, SET_SEP, ALIAS, AL_KV, AL_END = "\u26A2", "\u26A4", "\u26A5", "\u26A8", "\u26A7"

DEFAULT_SIZE = "583,827"


class FormatError(ValueError):
    pass


@dataclass
class Element:
    kind: str
    args: list[str] = field(default_factory=list)
    note: str = ""
    legs: list[list["Element"]] | None = None  # set only for kind == "Branch"

    def to_json(self) -> dict:
        if self.kind == "Branch":
            return {"branch": [[e.to_json() for e in leg] for leg in self.legs or []]}
        out: dict = {"kind": self.kind, "args": list(self.args)}
        if self.note:
            out["note"] = self.note
        return out

    @classmethod
    def from_json(cls, data: dict) -> "Element":
        if "branch" in data:
            return cls("Branch", legs=[[cls.from_json(e) for e in leg] for leg in data["branch"]])
        return cls(str(data["kind"]), [str(a) for a in data.get("args", [])], str(data.get("note", "")))


@dataclass
class Rung:
    elements: list[Element] = field(default_factory=list)
    comment: str = ""
    show_comment: bool | None = None

    def to_json(self) -> dict:
        out: dict = {"elements": [e.to_json() for e in self.elements]}
        if self.comment:
            out["comment"] = self.comment
        return out

    @classmethod
    def from_json(cls, data: dict) -> "Rung":
        return cls([Element.from_json(e) for e in data.get("elements", [])], str(data.get("comment", "")),
                   data.get("show_comment"))


@dataclass
class Project:
    name: str
    hardware: str
    main: list[Rung]
    initial: list[Rung] = field(default_factory=list)
    aliases: dict[str, str] = field(default_factory=dict)
    version: str = "360"
    password_enabled: str = "False"
    input_filters: list[str] = field(default_factory=lambda: ["3"] * 16)
    settings_tail: str = "True"
    password: str = "outseal"
    size_initial: str = DEFAULT_SIZE
    size_main: str = DEFAULT_SIZE
    legacy_tail: str | None = None  # pre-3.6 files: kept verbatim instead of a settings block

    def to_json(self) -> dict:
        return {
            "name": self.name, "hardware": self.hardware,
            "initial": [r.to_json() for r in self.initial if r.elements or r.comment],
            "main": [r.to_json() for r in self.main],
            "aliases": dict(self.aliases),
        }

    @classmethod
    def from_json(cls, data: dict) -> "Project":
        return cls(
            name=str(data["name"]), hardware=str(data["hardware"]),
            main=[Rung.from_json(r) for r in data.get("main", [])],
            initial=[Rung.from_json(r) for r in data.get("initial", [])],
            aliases={str(k): str(v) for k, v in data.get("aliases", {}).items()},
        )


# -- encoding -------------------------------------------------------------
_TITIK = EL + "Titik" + EL_ARGS + EL_END


def _encode_element(e: Element) -> str:
    if e.kind == "Branch":
        legs = "".join(BR + _TITIK + "".join(_encode_element(x) for x in leg) + _TITIK + BR_END
                       for leg in e.legs or [])
        return EL + "Branch" + EL_ARGS + legs + EL_END
    for text in [e.kind, e.note, *e.args]:
        _reject_delimiters(text)
    return EL + e.kind + EL_ARGS + "".join(a + ARG for a in e.args) + e.note + EL_END


def _encode_rung(r: Rung) -> str:
    _reject_delimiters(r.comment)
    show = bool(r.comment) if r.show_comment is None else r.show_comment
    return (RUNG + _TITIK + "".join(_encode_element(e) for e in r.elements) + _TITIK
            + CMT + r.comment + CMT + ("True" if show else "False") + RUNG_END)


def _encode_diagram(name: str, rungs: list[Rung], is_main: bool, size: str) -> str:
    rungs = rungs or [Rung()]
    return (DIAG + name + SEP + size + SEP + ("True" if is_main else "False") + SEP
            + SEP.join(_encode_rung(r) for r in rungs) + DIAG_END)


def encode(project: Project) -> str:
    for text in [project.name, project.hardware, *project.aliases, *project.aliases.values()]:
        _reject_delimiters(text)
    s = D_VER + project.version + D_HDR + project.name + D_HDR + project.hardware + D_HDR_END + STAR
    s += (D_INIT + _encode_diagram("Initial", project.initial, False, project.size_initial)
          + D_MAIN + _encode_diagram("Main", project.main, True, project.size_main) + D_DIAG_END + STAR)
    if project.legacy_tail is not None:
        s += project.legacy_tail
    else:
        s += (SETTINGS + project.password + SET_SEP + project.password_enabled + SET_SEP
              + "".join(f + SET_SEP for f in project.input_filters) + project.settings_tail + SET_SEP + STAR)
    if project.legacy_tail is None or project.aliases:
        s += ALIAS + "".join(k + AL_KV + v + AL_END for k, v in project.aliases.items())
    return s


def _reject_delimiters(text: str) -> None:
    bad = [c for c in text if "\u2400" <= c <= "\u27ff"]
    if bad:
        raise FormatError(f"text contains a reserved delimiter character U+{ord(bad[0]):04X}: {text!r}")


# -- decoding -------------------------------------------------------------
class _Reader:
    def __init__(self, text: str):
        self.t, self.i = text, 0

    def expect(self, token: str) -> None:
        if not self.t.startswith(token, self.i):
            raise FormatError(f"expected U+{ord(token[0]):04X} at {self.i}, got {self.t[self.i:self.i + 12]!r}")
        self.i += len(token)

    def peek(self, token: str) -> bool:
        return self.t.startswith(token, self.i)

    def until(self, *stops: str) -> str:
        j = min((k for k in (self.t.find(s, self.i) for s in stops) if k >= 0), default=-1)
        if j < 0:
            raise FormatError(f"unterminated field at {self.i}")
        out, self.i = self.t[self.i:j], j
        return out


def _read_titik(r: _Reader) -> None:
    r.expect(_TITIK)


def _read_element(r: _Reader) -> Element:
    r.expect(EL)
    kind = r.until(EL_ARGS)
    r.expect(EL_ARGS)
    if kind == "Branch":
        legs = []
        while r.peek(BR):
            r.expect(BR)
            _read_titik(r)
            leg = []
            while not r.peek(_TITIK):
                leg.append(_read_element(r))
            _read_titik(r)
            r.expect(BR_END)
            legs.append(leg)
        r.expect(EL_END)
        return Element("Branch", legs=legs)
    args = []
    body = r.until(EL_END)
    r.expect(EL_END)
    parts = body.split(ARG)
    args, note = parts[:-1], parts[-1]
    return Element(kind, args, note)


def _read_rung(r: _Reader) -> Rung:
    r.expect(RUNG)
    _read_titik(r)
    elements = []
    while not r.peek(_TITIK):
        elements.append(_read_element(r))
    _read_titik(r)
    r.expect(CMT)
    comment = r.until(CMT)
    r.expect(CMT)
    show = r.until(RUNG_END)
    r.expect(RUNG_END)
    return Rung(elements, comment, show == "True")


def _read_diagram(r: _Reader) -> tuple[str, str, list[Rung]]:
    r.expect(DIAG)
    name = r.until(SEP); r.expect(SEP)
    size = r.until(SEP); r.expect(SEP)
    r.until(SEP); r.expect(SEP)
    rungs = [_read_rung(r)]
    while r.peek(SEP):
        r.expect(SEP)
        rungs.append(_read_rung(r))
    r.expect(DIAG_END)
    return name, size, rungs



def decode(text: str) -> Project:
    r = _Reader(text)
    r.expect(D_VER)
    version = r.until(D_HDR); r.expect(D_HDR)
    name = r.until(D_HDR); r.expect(D_HDR)
    hardware = r.until(D_HDR_END); r.expect(D_HDR_END); r.expect(STAR)
    r.expect(D_INIT)
    _, size_i, initial = _read_diagram(r)
    r.expect(D_MAIN)
    _, size_m, main = _read_diagram(r)
    r.expect(D_DIAG_END); r.expect(STAR)
    project = Project(name, hardware, main, initial, version=version,
                      size_initial=size_i, size_main=size_m)
    if r.peek(SETTINGS):
        r.expect(SETTINGS)
        fields = r.until(STAR).split(SET_SEP)
        r.expect(STAR)
        if len(fields) >= 19:
            project.password, project.password_enabled = fields[0], fields[1]
            project.input_filters, project.settings_tail = fields[2:18], fields[18]
    else:  # pre-3.6 files end with a plain-text note instead of a settings block
        end = r.t.find(ALIAS, r.i)
        project.legacy_tail = r.t[r.i:end if end >= 0 else len(r.t)]
        r.i = end if end >= 0 else len(r.t)
    if r.peek(ALIAS):
        r.expect(ALIAS)
        for pair in r.t[r.i:].split(AL_END):
            if pair:
                k, _, v = pair.partition(AL_KV)
                project.aliases[k] = v
    return project


# -- files ----------------------------------------------------------------
def read_text(path: str | Path) -> str:
    data = Path(path).read_bytes()
    start = data.find(b"\x1f\x8b")
    if start < 0 or data[:start] != BANNER:
        raise FormatError(f"{path} is not an Outseal Studio project")
    return gzip.decompress(data[start:]).decode("utf-16-le")


def write_text(path: str | Path, text: str) -> None:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as stream:
        stream.write(text.encode("utf-16-le"))
    Path(path).write_bytes(BANNER + buffer.getvalue())


def read_project(path: str | Path) -> Project:
    return decode(read_text(path))


def write_project(path: str | Path, project: Project) -> None:
    write_text(path, encode(project))
