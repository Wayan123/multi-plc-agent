"""Delta backend: validation, IL generation, DVP word codec and .dvp patching."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from delta_mcp import dvp, server  # noqa: E402
from delta_mcp.il import decode, device_notes, encode, expected_il, il_text, parse_il_line, validate  # noqa: E402

TEMPLATE = server.TEMPLATES / "SS2.dvp"


def c(addr, kind="NO", **kw):
    return {"kind": kind, "args": [addr], **kw}


CONVEYOR = [
    {"comment": "Run request", "elements": [{"branch": [[c("X0", note="Start PB")], [c("M0")]]},
                                            c("X1", "NC", note="Stop PB"), c("X2", "NC", note="E-stop"),
                                            {"kind": "OUT", "args": ["M0"]}]},
    {"elements": [c("M0"), {"kind": "TMR", "args": ["T0", "K30"]}]},
    {"elements": [c("M0"), c("T0", "NC"), {"kind": "OUT", "args": ["Y1"], "note": "Warning horn"}]},
    {"elements": [c("M0"), c("T0"), {"kind": "OUT", "args": ["Y0"], "note": "Conveyor motor"}]},
    {"elements": [c("X3"), c("Y0"), {"kind": "CNT", "args": ["C0", "K10"]}]},
    {"elements": [c("X4"), {"kind": "RST", "args": ["C0"]}]},
    {"elements": [c("C0"), {"kind": "OUT", "args": ["Y2"]}]},
]
CONVEYOR_IL = ["LD X0", "OR M0", "ANI X1", "ANI X2", "OUT M0", "LD M0", "TMR T0 K30", "LD M0", "ANI T0",
               "OUT Y1", "LD M0", "AND T0", "OUT Y0", "LD X3", "AND Y0", "CNT C0 K10", "LD X4", "RST C0",
               "LD C0", "OUT Y2", "END"]
# Program words WPLSoft 2.52 saved for CONVEYOR_IL (entered in Instruction List mode, DVP-SS2)
CONVEYOR_WORDS = [0x2400, 0x6800, 0x5401, 0x5402, 0xC800, 0x2800, 0x0003, 0x8100, 0x801E, 0x8000,
                  0x2800, 0x5600, 0xC501, 0x2800, 0x4600, 0xC500, 0x2403, 0x4500, 0x0005, 0x8300,
                  0x800A, 0x8000, 0x2404, 0x0007, 0x8600, 0x840E, 0x2E00, 0xC502, 0x000F]

# Further words copied from WPLSoft (Edit > Copy, clipboard format CF_INST)
OBSERVED = {
    "LD X7": [0x2407], "LD X10": [0x2408], "LD X377": [0x24FF], "LDI Y17": [0x350F], "LD Y377": [0x25FF],
    "LD M255": [0x28FF], "LD M256": [0x2900], "LD M1000": [0x2BE8], "LD M1535": [0x2DFF],
    "LD M1536": [0x0202, 0x8400, 0x8010], "LD M4095": [0x0202, 0x84FF, 0x8019],
    "OUT M2000": [0x020C, 0x84D0, 0x8011], "LDI M2000": [0x0203, 0x84D0, 0x8011],
    "SET M2000": [0x020D, 0x84D0, 0x8011], "RST M2000": [0x0007, 0x84D0, 0x8011],
    "LD S0": [0x2000], "LD S1023": [0x23FF], "LD T255": [0x26FF], "LD C199": [0x2EC7], "LD T199": [0x26C7],
    "ORI X1": [0x7401], "ORB": [0xFFF9], "ANB": [0xFFF8], "MPS": [0xFFFA], "MRD": [0xFFFB], "MPP": [0xFFFC],
    "SET Y0": [0xD500], "SET S3": [0xD003], "RST Y0": [0x0007, 0x8400, 0x8005], "RST S9": [0x0007, 0x8409, 0x8000],
    "RST T0": [0x0007, 0x8600, 0x8206], "RST T200": [0x0007, 0x86C8, 0x8206],
    "RST C199": [0x0007, 0x86C7, 0x840E], "OUT S7": [0xC007],
    "TMR T200 K32767": [0x0003, 0x81C8, 0x80FF, 0x807F], "CNT C199 K32767": [0x0005, 0x83C7, 0x80FF, 0x807F],
    "OUT Y377": [0xC5FF],
}


def test_conveyor_il_and_words_match_wplsoft():
    assert validate(CONVEYOR) == []
    il = expected_il(CONVEYOR)
    assert il_text(il) == CONVEYOR_IL
    assert encode(il) == CONVEYOR_WORDS
    assert il_text(decode(CONVEYOR_WORDS + [0xFFFF])) == CONVEYOR_IL


@pytest.mark.parametrize("line, words", sorted(OBSERVED.items()))
def test_observed_encodings_round_trip(line, words):
    assert encode([parse_il_line(line)]) == words
    assert il_text(decode(words)) == [line]


def test_decode_marks_unknown_words():
    assert decode([0x0101, 0x000F]) == [("?", ("0x0101",)), ("END", ())]


def test_nested_branch_il():
    rung = {"elements": [{"branch": [[c("X0"), c("X1")], [c("M0"), {"branch": [[c("X2")], [c("X3")]]}]]},
                         c("X4"), {"kind": "OUT", "args": ["Y0"]}]}
    assert il_text(expected_il([rung])) == ["LD X0", "AND X1", "LD M0", "LD X2", "OR X3", "ANB", "ORB",
                                            "AND X4", "OUT Y0", "END"]


@pytest.mark.parametrize("rung, fragment", [
    ({"elements": [c("X0")]}, "at least one contact and one output"),
    ({"elements": [c("X8"), {"kind": "OUT", "args": ["Y0"]}]}, "octal"),
    ({"elements": [c("X0"), {"kind": "OUT", "args": ["X1"]}]}, "Y, M or S"),
    ({"elements": [c("X0"), {"kind": "OUT", "args": ["M4096"]}]}, "out of range"),
    ({"elements": [c("X0"), {"kind": "TMR", "args": ["C0", "K3"]}]}, "needs a T device"),
    ({"elements": [c("X0"), {"kind": "TMR", "args": ["T0", "30"]}]}, "K1..K32767"),
    ({"elements": [c("X0"), {"kind": "CNT", "args": ["C200", "K3"]}]}, "16-bit"),
    ({"elements": [c("D0"), {"kind": "OUT", "args": ["Y0"]}]}, "not a DVP bit address"),
    ({"elements": [{"kind": "OUT", "args": ["Y0"]}, c("X0")]}, "last element"),
    ({"elements": [{"branch": [[c("X0")]]}, {"kind": "OUT", "args": ["Y0"]}]}, "two legs"),
    ({"elements": [c("X0", note="a$&b"), {"kind": "OUT", "args": ["Y0"]}]}, "'$&'"),
])
def test_validate_rejects(rung, fragment):
    messages = [f.message for f in validate([rung])]
    assert any(fragment in m for m in messages), messages


def test_patch_template_round_trip():
    data = TEMPLATE.read_bytes()
    assert dvp.read_il(data) == []
    notes = device_notes(CONVEYOR, {"X4": "Reset"})
    out = dvp.patch(data, expected_il(CONVEYOR), notes)
    assert il_text(dvp.read_il(out)) == CONVEYOR_IL
    assert dvp.program_area(out)[1] == dvp.program_area(data)[1] == 7920
    comments = dvp.device_comments(out)
    assert comments["X0"] == "Start PB" and comments["X4"] == "Reset" and comments["Y0"] == "Conveyor motor"
    assert not any(a.startswith(("M1", "D1")) for a in comments)  # template carries no vendor preset texts
    assert out[:0x100] == data[:0x100] and out.endswith(b"<PrjectEnd>\n")


def test_patch_rejects_oversized_program():
    with pytest.raises(dvp.DvpError):
        dvp.patch(TEMPLATE.read_bytes(), [("LD", ("X0",))] * 7921, {})


def test_segment_comment_parse():
    data = b"x<DataEnd>\n<SegCmt>\n<0><Cnt=19>\nRun request seal-in<3><Cnt=11>\nStart delay</SegCmt>\n"
    assert dvp.segment_comments(data) == [(0, "Run request seal-in"), (3, "Start delay")]


def test_server_write_requires_flag_and_validates(tmp_path):
    off = server.Server(None, None, allow_write=False)
    with pytest.raises(PermissionError):
        off.call("new_project", {"path": str(tmp_path / "a.dvp")})
    on = server.Server(None, None, allow_write=True)
    made = on.call("new_project", {"path": str(tmp_path / "a.dvp")})
    with pytest.raises(FileExistsError):
        on.call("new_project", {"path": made["path"]})
    bad = on.call("write_ladder", {"path": made["path"], "rungs": [{"elements": [c("X0")]}]})
    assert bad["written"] is False and bad["findings"]
    good = on.call("validate", {"rungs": CONVEYOR})
    assert good["ok"] and good["expected_il"] == CONVEYOR_IL
    assert on.call("read_il", {"path": made["path"]})["il"] == []
    with pytest.raises(RuntimeError):  # GUI step needs --gui-python
        on.call("write_ladder", {"path": made["path"], "rungs": CONVEYOR})
    assert on.call("list_templates", {})["templates"] == ["SS2"]


def test_win_path():
    assert server._win_path("/mnt/d/A B/c.dvp") == "D:\\A B\\c.dvp"
    assert server._win_path("D:\\x.dvp") == "D:\\x.dvp"
