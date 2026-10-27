"""Haiwell backend: rung validation, keystroke plan and IL comparison."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from haiwell_mcp import server  # noqa: E402
from haiwell_mcp.ladder import expected_il, il_text, parse_il, plan, validate  # noqa: E402


def c(addr, kind="NO", **kw):
    return {"kind": kind, "args": [addr], **kw}


SEAL_IN = {"comment": "Run request", "elements": [
    {"branch": [[c("X0")], [c("M0")]]}, c("X1"), c("C0", "NC"), {"kind": "OUT", "args": ["M0"]}]}

# Observed export of HW_Exp2 (Haiwell Happy V2.2.13): Tools > Convert program to IL
OBSERVED_IL = """Main program: [PGB:MainLD]\r
LD          X0\r
OR          M0\r
AND         X1\r
ANDI        C0\r
OUT         M0\r
LD          M0\r
TON.1s      30, T0, TV0\r
\r
\r
Main program: [PGB:MainIL]\r
OUT         ????, ????\r
\r
END\r
"""


def test_expected_il_matches_observed_export():
    rungs = [SEAL_IN, {"elements": [c("M0"), {"kind": "TON", "args": ["T0", "30"]}]}]
    assert expected_il(rungs) == parse_il(OBSERVED_IL, "MainLD")


def test_parse_il_selects_block():
    assert parse_il(OBSERVED_IL, "MainIL") == [("OUT", ["????", "????"])]


def test_multi_contact_leg_and_mid_rung_branch_il():
    # observed: LD X0 / LD M0 / AND X6 / ORB / AND X1 / LD X2 / OR X7 / ANDB / AND X3 / OUT Y10
    rung = {"elements": [
        {"branch": [[c("X0")], [c("M0"), c("X6")]]}, c("X1"),
        {"branch": [[c("X2")], [c("X7")]]}, c("X3"), {"kind": "OUT", "args": ["Y10"]}]}
    assert il_text(expected_il([rung])) == [
        "LD          X0", "LD          M0", "AND         X6", "ORB", "AND         X1",
        "LD          X2", "OR          X7", "ANDB", "AND         X3", "OUT         Y10"]


@pytest.mark.parametrize("rung, fragment", [
    ({"elements": [c("X0")]}, "at least one contact and one output"),
    ({"elements": [c("X0"), {"kind": "OUT", "args": ["X1"]}]}, "writable bit"),
    ({"elements": [c("X0"), {"kind": "TON", "args": ["C0", "3"]}]}, "timer like T0"),
    ({"elements": [c("X0"), {"kind": "CTU", "args": ["C0", "0"]}]}, "1..32767"),
    ({"elements": [{"kind": "OUT", "args": ["Y0"]}, c("X0")]}, "last element"),
    ({"elements": [{"branch": [[c("X0"), c("X1")], [c("X2")]]}, {"kind": "OUT", "args": ["Y0"]}]},
     "first leg"),
    ({"elements": [{"branch": [[c("X0")]]}, {"kind": "OUT", "args": ["Y0"]}]}, "two legs"),
    ({"elements": [c("D0"), {"kind": "OUT", "args": ["Y0"]}]}, "bit address"),
    ({"elements": [c("X0", note="a//b"), {"kind": "OUT", "args": ["Y0"]}]}, "'//'"),
])
def test_validate_rejects(rung, fragment):
    messages = [f.message for f in validate([rung])]
    assert any(fragment in m for m in messages), messages


def test_plan_adds_branch_before_output_and_comments_once():
    steps = [s.get("k", s) for s in plan([SEAL_IN, {"elements": [c("M0"), {"kind": "OUT", "args": ["Y0"]}]}],
                                         {"M0": "Run (req)"})["steps"]]
    first = steps[: steps.index("^l", 3)]
    # main line X0 X1 C0, back two cells to X0, parallel M0, return two cells, then the coil
    assert first[4:] == ["{F9}", "{ENTER}", "X0{ENTER}", "{F9}", "{ENTER}", "X1{ENTER}",
                         "{F9}", "^2", "{ENTER}", "C0{ENTER}", "{LEFT}", "{LEFT}",
                         "{F10}", "{ENTER}", "M0//Run {(}req{)}{ENTER}", "{UP}",
                         "{RIGHT}", "{RIGHT}", "{F11}", "{ENTER}", "M0{ENTER}"]
    assert first[:4] == ["^a", "{DEL}", "^l", {"comment": "Run request"}]
    assert steps.count("M0//Run {(}req{)}{ENTER}") == 1


def test_plan_return_walk_counts_wide_branch_cells():
    # GUI-verified: a two-contact leg makes its branch two cells wide, so the
    # walk from the first contact to the last (X3) needs 2 + 1 + 1 RIGHT presses
    rung = {"elements": [
        {"branch": [[c("X0")], [c("M0"), c("X6", "NC")]]}, c("X1"),
        {"branch": [[c("X2")], [c("X7")]]}, c("X3"), {"kind": "SET", "args": ["Y5"]}]}
    steps = [s["k"] for s in plan([rung])["steps"] if "k" in s]
    after_branches = len(steps) - steps[::-1].index("{UP}")
    # 4 walk presses, then SET's own RIGHT onto the output cell and its first letter
    assert steps[after_branches:after_branches + 6] == ["{RIGHT}"] * 5 + ["S"]


def test_plan_reports_aliases_not_in_ladder():
    assert plan([SEAL_IN], {"Y7": "Spare"})["unapplied_aliases"] == {"Y7": "Spare"}


def test_server_write_requires_flag_and_validates(tmp_path):
    off = server.Server(None, None, allow_write=False)
    with pytest.raises(PermissionError):
        off.call("new_project", {"path": str(tmp_path / "a.gpc")})
    on = server.Server(None, None, allow_write=True)
    made = on.call("new_project", {"path": str(tmp_path / "a.gpc")})
    assert (tmp_path / "a.gpc").read_bytes()[:2] == (server.TEMPLATES / "AT16S0T.gpc").read_bytes()[:2]
    with pytest.raises(FileExistsError):
        on.call("new_project", {"path": made["path"]})
    bad = on.call("write_ladder", {"path": made["path"], "rungs": [{"elements": [c("X0")]}]})
    assert bad["written"] is False and bad["findings"]
    good = on.call("validate", {"rungs": [SEAL_IN]})
    assert good["ok"] and good["expected_il"][0] == "LD          X0"
    assert json.dumps(on.call("list_templates", {}))


def test_win_path():
    assert server._win_path("/mnt/d/A B/c.gpc") == "D:\\A B\\c.gpc"
    assert server._win_path("D:\\x.gpc") == "D:\\x.gpc"
