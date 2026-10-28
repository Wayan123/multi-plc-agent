"""CODESYS backend: validation, PLCopen generation and logic comparison.

The CODESYS_EXPORT fixture is the shape CODESYS V3.5 SP21 exports after it
imported a generated POU: localIds renumbered, network comment and title
reordered, and a vendor ParallelBranch element added. The comparison must
read the same logic from it.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from codesys_mcp import server  # noqa: E402
from codesys_mcp.ladder import expected_logic, parse_logic, to_plcopen, validate  # noqa: E402


def c(name, kind="NO"):
    return {"kind": kind, "args": [name]}


VARS = [{"name": n, "type": "BOOL"} for n in ("Start", "Run", "StopNC", "Motor", "Reset")] + \
       [{"name": "In0", "type": "BOOL", "address": "%IX0.0"}]
SEAL = {"comment": "Run request", "elements": [{"branch": [[c("Start")], [c("Run")]]}, c("StopNC"), {"kind": "OUT", "args": ["Run"]}]}
TIMER = {"comment": "Delay", "elements": [c("Run"), {"kind": "TON", "args": ["T1", "T#3S"]}]}
AFTER = {"comment": "", "elements": [c("T1.Q"), {"kind": "OUT", "args": ["Motor"]}]}

CODESYS_EXPORT = """\ufeff<?xml version="1.0" encoding="utf-8"?>
<project xmlns="http://www.plcopen.org/xml/tc6_0200"><types><pous><pou name="PLC_PRG" pouType="program"><body><LD>
<leftPowerRail localId="0"><position x="0" y="0" /><connectionPointOut formalParameter="none" /></leftPowerRail>
<comment localId="3" height="0" width="0"><position x="0" y="0" /><content><xhtml xmlns="http://www.w3.org/1999/xhtml">Run request</xhtml></content></comment>
<vendorElement localId="2"><position x="0" y="0" /><alternativeText><xhtml xmlns="http://www.w3.org/1999/xhtml" /></alternativeText></vendorElement>
<contact localId="5"><position x="0" y="0" /><connectionPointIn><connection refLocalId="0" /></connectionPointIn><connectionPointOut /><variable>Start</variable></contact>
<contact localId="6"><position x="0" y="0" /><connectionPointIn><connection refLocalId="0" /></connectionPointIn><connectionPointOut /><variable>Run</variable></contact>
<contact localId="7"><position x="0" y="0" /><connectionPointIn><connection refLocalId="5" /><connection refLocalId="6" /></connectionPointIn><connectionPointOut /><variable>StopNC</variable></contact>
<coil localId="8"><position x="0" y="0" /><connectionPointIn><connection refLocalId="7" /></connectionPointIn><connectionPointOut /><variable>Run</variable></coil>
<vendorElement localId="4"><position x="0" y="0" /><alternativeText><xhtml xmlns="http://www.w3.org/1999/xhtml">ParallelBranch</xhtml></alternativeText></vendorElement>
<comment localId="11" height="0" width="0"><position x="0" y="0" /><content><xhtml xmlns="http://www.w3.org/1999/xhtml">Delay</xhtml></content></comment>
<contact localId="13"><position x="0" y="0" /><connectionPointIn><connection refLocalId="0" /></connectionPointIn><connectionPointOut /><variable>Run</variable></contact>
<inVariable localId="14"><position x="0" y="0" /><connectionPointOut /><expression>T#3S</expression></inVariable>
<block localId="12" typeName="TON" instanceName="T1"><position x="0" y="0" /><inputVariables>
<variable formalParameter="IN"><connectionPointIn><connection refLocalId="13" /></connectionPointIn></variable>
<variable formalParameter="PT"><connectionPointIn><connection refLocalId="14" /></connectionPointIn></variable>
</inputVariables><inOutVariables /><outputVariables><variable formalParameter="Q"><connectionPointOut /></variable></outputVariables></block>
<rightPowerRail localId="2147483647"><position x="0" y="0" /><connectionPointIn /></rightPowerRail>
</LD></body></pou></pous></types></project>"""


def test_codesys_export_reads_as_the_rungs_that_produced_it():
    assert parse_logic(CODESYS_EXPORT, "PLC_PRG") == expected_logic([SEAL, TIMER])


def test_generated_xml_round_trips_to_the_same_logic():
    ctu = {"elements": [c("Start"), c("Motor"), {"kind": "CTU", "args": ["Batch", "10", "Reset"]}]}
    nested = {"elements": [{"branch": [[c("Start"), {"branch": [[c("Run")], [c("Reset", "NC")]]}], [c("Batch.Q")]]},
                           {"kind": "SET", "args": ["Motor"]}]}
    rungs = [SEAL, TIMER, AFTER, ctu, nested]
    xml = to_plcopen("PLC_PRG", VARS, rungs)
    ET.fromstring(xml.encode())  # well-formed
    assert parse_logic(xml, "PLC_PRG") == expected_logic(rungs)
    assert expected_logic([nested])[0]["logic"] == "Batch.Q OR (NOT Reset AND Start) OR (Run AND Start)"
    assert expected_logic([SEAL])[0]["logic"] == "(Run AND StopNC) OR (Start AND StopNC)"
    assert expected_logic([ctu])[0]["params"] == {"PV": "10", "RESET": "Reset"}


def test_declaration_lists_variables_and_fb_instances():
    xml = to_plcopen("PLC_PRG", VARS, [SEAL, TIMER])
    assert "In0 AT %IX0.0 : BOOL;" in xml and "T1 : TON;" in xml


@pytest.mark.parametrize("variables, rungs, fragment", [
    (VARS, [{"elements": [c("Start")]}], "at least one contact and one output"),
    (VARS, [{"elements": [c("Nope"), {"kind": "OUT", "args": ["Motor"]}]}], "declared BOOL"),
    (VARS, [{"elements": [c("T9.Q"), {"kind": "OUT", "args": ["Motor"]}]}], "declared BOOL"),
    (VARS, [{"elements": [c("Start"), {"kind": "OUT", "args": ["In0"]}]}], "input address"),
    (VARS, [{"elements": [c("Start"), {"kind": "TON", "args": ["T1", "3"]}]}], "TIME literal"),
    (VARS, [{"elements": [c("Start"), {"kind": "CTU", "args": ["C1", "0", "Reset"]}]}], "1..32767"),
    (VARS, [{"elements": [c("Start"), {"kind": "TON", "args": ["Run", "T#1S"]}]}], "clashes"),
    (VARS + [{"name": "start", "type": "BOOL"}], [SEAL], "declared twice"),
    ([{"name": "X", "type": "BOOL", "address": "%IX0.9"}], [SEAL], "address"),
    ([{"name": "AND", "type": "BOOL"}], [SEAL], "IEC identifier"),
])
def test_validate_rejects(variables, rungs, fragment):
    messages = [f.message for f in validate("PLC_PRG", variables, rungs)]
    assert any(fragment in m for m in messages), messages


def test_write_requires_flag_suffix_and_valid_input(tmp_path):
    with pytest.raises(PermissionError):
        server.Server("missing.exe", "p", False).call("write_ladder", {"path": str(tmp_path / "a.project"), "rungs": [SEAL]})
    on = server.Server("missing.exe", "p", True)
    with pytest.raises(ValueError):
        on.call("write_ladder", {"path": str(tmp_path / "a.txt"), "variables": VARS, "rungs": [SEAL]})
    bad = on.call("write_ladder", {"path": str(tmp_path / "a.project"), "variables": VARS, "rungs": [{"elements": [c("Start")]}]})
    assert bad["written"] is False
    existing = tmp_path / "b.project"
    existing.write_text("x")
    with pytest.raises(FileExistsError):
        on.call("write_ladder", {"path": str(existing), "variables": VARS, "rungs": [SEAL]})
