"""Read and patch WPLSoft .dvp project files (observed with WPLSoft 2.52, DVP-SS2).

Layout seen in files saved by WPLSoft:
- 0x000..0x0FF  header; the byte at 0x5E is the key of the program area.
- 0x100..       program area: one 16-bit little-endian word per step, every
                byte XOR-ed with the key; unused steps read 0xFFFF. Its size is
                the PLC's step capacity (7920 steps on SS2).
- after it      plain-text sections "<TypeBegin>\\nFunction=<name>\\n<TypeEnd>\\n
                <DataBegin>\\n...<DataEnd>". Device comments are lines
                "X0$&Start PB" in "Function=Device Comment". Segment comments
                follow in "<SegCmt>\\n<row><Cnt=n>\\ntext...</SegCmt>" (row = ladder row),
                but they also need a binary <SMT> record in the ladder-layout
                area, so this module only reads them.
WPLSoft opens a file whose header was left unchanged after the program area
was rewritten (it does not check the header word at 0x56). The GUI driver
still saves the project once through WPLSoft after compiling so the header is
WPLSoft's own.
"""
from __future__ import annotations

import re

from .il import EMPTY, Instr, decode, encode

KEY_OFFSET = 0x5E
PROGRAM_OFFSET = 0x100
DEVICE_COMMENT = b"Function=Device Comment\n<TypeEnd>\n<DataBegin>\n"
SEG = re.compile(rb"<SegCmt>\n(.*?)</SegCmt>", re.S)
SEG_ENTRY = re.compile(rb"<(\d+)><Cnt=(\d+)>\n")


class DvpError(ValueError):
    pass


def _check(data: bytes) -> None:
    if len(data) < PROGRAM_OFFSET + 2 or b"<PrjectEnd>" not in data or DEVICE_COMMENT not in data:
        raise DvpError("not a WPLSoft .dvp project (missing program area or text sections)")


def program_area(data: bytes) -> tuple[int, int, list[int]]:
    """(key, capacity in steps, decrypted words of the whole program area)."""
    _check(data)
    key = data[KEY_OFFSET]
    words: list[int] = []
    end_seen = False
    for pos in range(PROGRAM_OFFSET, len(data) - 1, 2):
        w = (data[pos] ^ key) | ((data[pos + 1] ^ key) << 8)
        if w == EMPTY:
            end_seen = True
        elif end_seen:
            break
        words.append(w)
    if not end_seen:
        raise DvpError("program area end not found")
    return key, len(words), words


def program_words(data: bytes) -> list[int]:
    _, _, words = program_area(data)
    return words[: words.index(EMPTY)]


def read_il(data: bytes) -> list[Instr]:
    return decode(program_words(data))


def device_comments(data: bytes) -> dict[str, str]:
    _check(data)
    start = data.index(DEVICE_COMMENT) + len(DEVICE_COMMENT)
    body = data[start: data.index(b"<DataEnd>", start)]
    out = {}
    for line in body.decode("latin-1").split("\n"):
        addr, sep, text = line.partition("$&")
        if sep:
            out[addr] = text
    return out


def segment_comments(data: bytes) -> list[tuple[int, str]]:
    m = SEG.search(data)
    if not m:
        return []
    body, out, pos = m.group(1), [], 0
    while pos < len(body):
        e = SEG_ENTRY.match(body, pos)
        if not e:
            raise DvpError(f"unreadable segment comment at {body[pos:pos + 20]!r}")
        n = int(e.group(2))
        out.append((int(e.group(1)), body[e.end(): e.end() + n].decode("latin-1")))
        pos = e.end() + n
    return out


def patch(data: bytes, il: list[Instr], notes: dict[str, str]) -> bytes:
    """Replace the program and set device comments (other comments kept).

    Use an empty project as `data`: the binary ladder-layout area between the
    text sections is left as it is, and WPLSoft rebuilds the ladder from the
    program words only when that area is empty. Saving through WPLSoft
    afterwards (wplsoft_gui) writes a matching layout."""
    key, capacity, _ = program_area(data)
    words = encode(il)
    if len(words) > capacity:
        raise DvpError(f"program needs {len(words)} steps, the project holds {capacity}")
    words += [EMPTY] * (capacity - len(words))
    raw = b"".join(w.to_bytes(2, "little") for w in words)
    out = bytearray(data)
    out[PROGRAM_OFFSET: PROGRAM_OFFSET + len(raw)] = bytes(b ^ key for b in raw)
    out = bytes(out)

    start = out.index(DEVICE_COMMENT) + len(DEVICE_COMMENT)
    end = out.index(b"<DataEnd>", start)
    kept = [line for line in out[start:end].split(b"\n")
            if line and line.partition(b"$&")[0].decode("latin-1") not in notes]
    ours = [f"{a}$&{t}".encode("ascii") for a, t in notes.items()]
    body = b"".join(line + b"\n" for line in ours + kept)
    return out[:start] + body + out[end:]
