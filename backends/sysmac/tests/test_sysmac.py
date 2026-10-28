"""Sysmac Studio backend: validation, IEC 61131-10 XML generation and stored-listing read-back.

CONVEYOR_LISTING and LATCH_LISTING are the ladder sections Sysmac Studio 1.47 stored after
importing the XML that to_iec_xml() produced for CONVEYOR and LATCH (NX1P2-1040DT project,
Check All Programs: 0 errors). No vendor software is needed to run these tests.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sysmac_mcp import server  # noqa: E402
from sysmac_mcp.ladder import expected_logic, parse_listing, program_entity_pattern, to_iec_xml, validate  # noqa: E402


def c(name, kind="NO"):
    return {"kind": kind, "args": [name]}


VARS = [{"name": n, "type": "BOOL"} for n in
        ("StartPB", "StopPB", "EStop", "ProductSensor", "CountReset", "Run", "Horn", "Motor", "BatchDone")]
CONVEYOR = [
    {"comment": "Run request with seal-in", "elements": [{"branch": [[c("StartPB")], [c("Run")]]}, c("StopPB", "NC"),
                                                          c("EStop", "NC"), c("Batch.Q", "NC"), {"kind": "OUT", "args": ["Run"]}]},
    {"comment": "3 s start delay", "elements": [c("Run"), {"kind": "TON", "args": ["StartDelay", "T#3s"]}]},
    {"comment": "Warning horn while timing", "elements": [c("Run"), c("StartDelay.Q", "NC"), {"kind": "OUT", "args": ["Horn"]}]},
    {"comment": "Motor after delay", "elements": [c("Run"), c("StartDelay.Q"), {"kind": "OUT", "args": ["Motor"]}]},
    {"comment": "Count 10 products", "elements": [c("ProductSensor"), {"kind": "CTU", "args": ["Batch", "10", "CountReset"]}]},
    {"comment": "Batch done lamp", "elements": [c("Batch.Q"), {"kind": "OUT", "args": ["BatchDone"]}]},
]
LATCH_VARS = [{"name": n} for n in ("A", "B", "C", "D", "Q")]
LATCH = [
    {"elements": [c("A"), {"kind": "SET", "args": ["Q"]}]},
    {"elements": [c("B"), {"kind": "RST", "args": ["Q"]}]},
    {"comment": "nested", "elements": [{"branch": [[c("A"), {"branch": [[c("B")], [c("C", "NC")]]}], [c("D")]]},
                                       {"kind": "OUT", "args": ["Q"]}]},
]

CONVEYOR_LISTING = r'''{"CLs":[{"__type":"LD","Var":"StartPB"},{"__type":"LD","Ix":1,"Var":"Run","Y":1},{"__type":"LD","Ix":2,"Not":true,"Var":"StopPB","X":1},{"__type":"LD","Ix":3,"Not":true,"Var":"EStop","X":2},{"__type":"LD","Ix":4,"Not":true,"Var":"Batch.Q","X":3},{"__type":"ST","Ix":5,"Var":"Run","X":4}],"CMT":"Run request with seal-in","LRI":6,"RRI":7,"VLs":[{"Ix":8,"X":1}]}
{"CLs":[{"__type":"LD","Var":"Run"},{"__type":"FB","In":[{"__type":"PF","Arg":"In"},{"__type":"PRM","Arg":"PT","Ix":1,"Type":"TIME","Var":"T#3s"}],"Ix":3,"Name":"TON","Out":[{"__type":"PF","Arg":"Q"},{"__type":"PRM","Arg":"ET","Ix":2,"Type":"TIME","Var":""}],"X":1,"Var":"StartDelay"}],"CMT":"3 s start delay","LRI":4,"RRI":5,"VLs":[]}
{"CLs":[{"__type":"LD","Var":"Run"},{"__type":"LD","Ix":1,"Not":true,"Var":"StartDelay.Q","X":1},{"__type":"ST","Ix":2,"Var":"Horn","X":2}],"CMT":"Warning horn while timing","LRI":3,"RRI":4,"VLs":[]}
{"CLs":[{"__type":"LD","Var":"Run"},{"__type":"LD","Ix":1,"Var":"StartDelay.Q","X":1},{"__type":"ST","Ix":2,"Var":"Motor","X":2}],"CMT":"Motor after delay","LRI":3,"RRI":4,"VLs":[]}
{"CLs":[{"__type":"LD","Var":"ProductSensor"},{"__type":"FB","In":[{"__type":"PF","Arg":"CU","Up":true},{"__type":"PRM","Arg":"Reset","Ix":1,"Type":"BOOL","Var":"CountReset"},{"__type":"PRM","Arg":"PV","Ix":2,"Type":"INT","Var":"INT#10"}],"Ix":4,"Name":"CTU","Out":[{"__type":"PF","Arg":"Q"},{"__type":"PRM","Arg":"CV","Ix":3,"Type":"INT","Var":""}],"X":1,"Var":"Batch"}],"CMT":"Count 10 products","LRI":5,"RRI":6,"VLs":[]}
{"CLs":[{"__type":"LD","Var":"Batch.Q"},{"__type":"ST","Ix":1,"Var":"BatchDone","X":1}],"CMT":"Batch done lamp","LRI":2,"RRI":3,"VLs":[]}'''
LATCH_LISTING = r'''{"CLs":[{"__type":"LD","Var":"A"},{"__type":"ST","Ix":1,"S":true,"Var":"Q","X":1}],"LRI":2,"RRI":3,"VLs":[]}
{"CLs":[{"__type":"LD","Var":"B"},{"__type":"ST","Ix":1,"RS":true,"Var":"Q","X":1}],"LRI":2,"RRI":3,"VLs":[]}
{"CLs":[{"__type":"LD","Var":"A"},{"__type":"LD","Ix":1,"Var":"B","X":1},{"__type":"LD","Ix":2,"Not":true,"Var":"C","X":1,"Y":1},{"__type":"LD","Ix":3,"Var":"D","Y":2},{"__type":"HL","X":1,"Y":2},{"__type":"ST","Ix":4,"Var":"Q","X":2}],"CMT":"nested","LRI":5,"RRI":6,"VLs":[{"Ix":7,"X":1},{"Ix":8,"X":2},{"Ix":8,"X":2,"Y":1}]}'''


def test_sysmac_stored_listing_reads_as_the_rungs_that_produced_it():
    assert parse_listing(CONVEYOR_LISTING) == expected_logic(CONVEYOR)
    assert parse_listing(LATCH_LISTING) == expected_logic(LATCH)


def test_listing_logic_is_canonical():
    got = parse_listing(LATCH_LISTING)
    assert [g["kind"] for g in got] == ["SET", "RST", "OUT"]
    assert got[2]["logic"] == "(A AND B) OR (A AND NOT C) OR D"
    assert parse_listing(CONVEYOR_LISTING)[4]["params"] == {"Reset": "CountReset", "PV": "INT#10"}


def test_generated_xml_has_sysmac_shape():
    ns = {"p": "www.iec.ch/public/TC65SC65BWG7TF10", "xsi": "http://www.w3.org/2001/XMLSchema-instance"}
    root = ET.fromstring(to_iec_xml("Conveyor", VARS, CONVEYOR).encode("utf-8"))
    assert root.get("schemaVersion") == "1"
    assert root.find("p:Instances/p:Configuration/p:Resource", ns) is not None  # import rejects files without it
    prog = root.find("p:Types/p:GlobalNamespace/p:Program", ns)
    assert prog.get("name") == "Conveyor"
    declared = {v.get("name"): v.find("p:Type/p:TypeName", ns).text for v in prog.iter("{%s}Variable" % ns["p"])}
    assert declared["StartDelay"] == "TON" and declared["Batch"] == "CTU" and declared["Run"] == "BOOL"
    rungs = prog.findall(".//p:Rung", ns)
    assert len(rungs) == len(CONVEYOR)
    blocks = [b for b in prog.iter("{%s}FbdObject" % ns["p"]) if b.get("{%s}type" % ns["xsi"]) == "Block"]
    assert [(b.get("typeName"), b.get("instanceName")) for b in blocks] == [("TON", "StartDelay"), ("CTU", "Batch")]
    latch = ET.fromstring(to_iec_xml("L", LATCH_VARS, LATCH).encode("utf-8"))
    coils = [o.get("latch") for o in latch.iter("{%s}LdObject" % ns["p"]) if o.get("{%s}type" % ns["xsi"]) == "Coil"]
    assert coils == ["set", "reset", None]


def test_every_connection_refers_to_an_earlier_point():
    root = ET.fromstring(to_iec_xml("L", LATCH_VARS, LATCH).encode("utf-8"))
    for rung in root.iter("{www.iec.ch/public/TC65SC65BWG7TF10}Rung"):
        seen = set()
        for el in rung.iter():
            tag = el.tag.rsplit("}", 1)[-1]
            if tag == "Connection":
                assert el.get("refConnectionPointOutId") in seen
            if tag == "ConnectionPointOut":
                seen.add(el.get("connectionPointOutId"))


def test_conveyor_validates():
    assert validate("Conveyor", VARS, CONVEYOR) == []


@pytest.mark.parametrize("program, variables, rungs, fragment", [
    ("1bad", VARS, CONVEYOR, "not a valid identifier"),
    ("P", VARS + [{"name": "Run"}], CONVEYOR, "declared twice"),
    ("P", [{"name": "_x"}], [{"elements": [c("_x"), {"kind": "OUT", "args": ["_x"]}]}], "leading underscore"),
    ("P", [{"name": "A", "type": "LREAL"}], [{"elements": [c("A"), {"kind": "OUT", "args": ["A"]}]}], "type must be"),
    ("P", VARS, [{"elements": [c("Ghost"), {"kind": "OUT", "args": ["Run"]}]}], "declared BOOL"),
    ("P", VARS, [{"elements": [c("Run"), c("Motor")]}], "last element"),
    ("P", VARS, [{"elements": [c("Run"), {"kind": "TON", "args": ["T1", "3s"]}]}], "TIME literal"),
    ("P", VARS, [{"elements": [c("Run"), {"kind": "CTU", "args": ["C1", "0", "CountReset"]}]}], "1..32767"),
    ("P", VARS, [{"elements": [c("Run"), {"kind": "TON", "args": ["Run", "T#1s"]}]}], "clashes"),
    ("P", VARS, [{"elements": [{"branch": [[c("Run")]]}, {"kind": "OUT", "args": ["Motor"]}]}], "two legs"),
    ("P", VARS, [{"elements": [{"kind": "OUT", "args": ["Motor"]}]}], "at least one contact"),
    ("P", VARS, [], "no rungs"),
])
def test_validate_rejects(program, variables, rungs, fragment):
    messages = [f.message for f in validate(program, variables, rungs)]
    assert any(fragment in m for m in messages), messages


def test_server_gates_writes_and_verifies_logic():
    off = server.Server(None, None, allow_write=False)
    with pytest.raises(PermissionError):
        off.call("write_program", {"program": "Conveyor", "variables": VARS, "rungs": CONVEYOR})
    ok = off.call("validate", {"program": "Conveyor", "variables": VARS, "rungs": CONVEYOR})
    assert ok["ok"] and ok["iec_xml"].startswith("<?xml") and len(ok["expected_logic"]) == 6
    on = server.Server(None, None, allow_write=True)
    bad = on.call("write_program", {"program": "Conveyor", "variables": VARS, "rungs": [{"elements": [c("Run")]}]})
    assert bad["written"] is False
    with pytest.raises(RuntimeError):  # valid input still needs the Windows GUI driver
        on.call("write_program", {"program": "Conveyor", "variables": VARS, "rungs": CONVEYOR})
    good = {"imported": True, "sections": [{"name": "Section0", "listing": CONVEYOR_LISTING}], "ok": True}
    assert server._verify(dict(good), "Conveyor", CONVEYOR)["logic_matches"] is True
    wrong = server._verify(dict(good), "Conveyor", CONVEYOR[:5] + [{"elements": [c("Run"), {"kind": "OUT", "args": ["BatchDone"]}]}])
    assert wrong["ok"] is False and wrong["logic_matches"] is False


def test_wsl_paths_become_windows_paths():
    assert server._win("/mnt/d/KERJA/x y/a.xml") == "D:\\KERJA\\x y\\a.xml"
    assert server._win("C:\\t\\a.xml") == "C:\\t\\a.xml"


def test_tools_list_names_have_no_prefix():
    names = [t["name"] for t in server._tools()]
    assert names == ["list_devices", "validate", "write_program", "build", "read_program"]


def test_program_lookup_skips_solution_entity_with_same_name():
    oem = ('<Entity type="Solution" subtype="" id="11" name="Conveyor">'
           '<Entity type="Program" subtype="MultipartLadder" id="2a" name="Conveyor">')
    m = program_entity_pattern("Conveyor").search(oem)
    assert m and m.group(0).startswith('<Entity type="Program"')
    assert program_entity_pattern("Conv").search(oem) is None
