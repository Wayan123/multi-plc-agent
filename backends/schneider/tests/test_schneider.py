"""Schneider (Machine Expert - Basic) backend: validation, IL, .smbp write/read-back and MCP tools.

EXPECTED_CONVEYOR_IL is what Machine Expert - Basic V1.3 showed in its IL editor
for the conveyor project after Compile Program reported "No error" (operator
padding normalised), and what it kept after saving the project.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from schneider_mcp import codec  # noqa: E402
from schneider_mcp.server import Server, _tools  # noqa: E402

TEMPLATE = codec.TEMPLATES / f"{codec.DEFAULT_TEMPLATE}.smbp"


def c(addr, kind="NO", **kw):
    return {"kind": kind, "args": [addr], **kw}


def out(addr, kind="OUT", **kw):
    return {"kind": kind, "args": [addr], **kw}


CONVEYOR_RUNGS = [
    {"name": "Run", "comment": "Seal-in", "elements": [
        {"branch": [[c("%I0.0", note="Start push button")], [c("%M0")]]},
        c("%I0.1", "NC", note="Stop push button"), c("%I0.2", note="E-stop healthy (NC contact)"),
        c("%C0.D", "NC"), out("%M0", note="Run request")]},
    {"name": "Start delay", "elements": [c("%M0"), {"kind": "TON", "args": ["%TM0", "3", "1s"], "note": "Start delay"}]},
    {"name": "Horn", "elements": [c("%M0"), c("%TM0.Q", "NC"), out("%Q0.1", note="Warning horn")]},
    {"name": "Motor", "elements": [c("%M0"), c("%TM0.Q"), out("%Q0.0", note="Conveyor motor")]},
    {"name": "Count", "elements": [c("%I0.3", "RE", note="Product sensor"), c("%Q0.0"),
                                   {"kind": "CTU", "args": ["%C0", "10", "%I0.4"], "note": "Products per batch"}]},
    {"name": "Batch done", "elements": [c("%C0.D"), out("%Q0.2", note="Batch done lamp")]},
]
SYMBOLS = {"%I0.0": "START_PB", "%I0.1": "STOP_PB", "%I0.2": "ESTOP", "%I0.3": "PRODUCT_SENSOR",
           "%I0.4": "COUNT_RESET", "%Q0.0": "MOTOR", "%Q0.1": "HORN", "%Q0.2": "BATCH_DONE",
           "%M0": "RUN", "%TM0": "T_START_DELAY", "%C0": "C_PRODUCTS"}
EXPECTED_CONVEYOR_IL = [
    ["LD %I0.0", "OR %M0", "ANDN %I0.1", "AND %I0.2", "ANDN %C0.D", "ST %M0"],
    ["BLK %TM0", "LD %M0", "IN", "END_BLK"],
    ["LD %M0", "ANDN %TM0.Q", "ST %Q0.1"],
    ["LD %M0", "AND %TM0.Q", "ST %Q0.0"],
    ["BLK %C0", "LD %I0.4", "R", "LDR %I0.3", "AND %Q0.0", "CU", "END_BLK"],
    ["LD %C0.D", "ST %Q0.2"],
]


def test_conveyor_il():
    assert not codec.validate(CONVEYOR_RUNGS, SYMBOLS)
    assert codec.expected_il(CONVEYOR_RUNGS) == EXPECTED_CONVEYOR_IL


@pytest.mark.parametrize("elements, il", [
    # IL forms accepted by Machine Expert - Basic V1.3 (compiled with "No error")
    ([{"branch": [[c("%I0.0"), c("%I0.1")], [c("%M1")]]}, out("%Q0.0")],
     ["LD %I0.0", "AND %I0.1", "OR %M1", "ST %Q0.0"]),
    ([c("%I0.0"), {"branch": [[c("%I0.1")], [c("%I0.2")]]}, c("%I0.3"), out("%Q0.2")],
     ["LD %I0.0", "AND( %I0.1", "OR %I0.2", ")", "AND %I0.3", "ST %Q0.2"]),
    ([c("%I0.0"), {"branch": [[c("%I0.1"), c("%I0.5")], [c("%I0.2"), c("%I0.6")]]}, out("%Q0.3")],
     ["LD %I0.0", "AND( %I0.1", "AND %I0.5", "OR( %I0.2", "AND %I0.6", ")", ")", "ST %Q0.3"]),
    ([{"branch": [[c("%I0.0")], [c("%M1"), c("%M2")]]}, out("%Q0.1")],
     ["LD %I0.0", "OR( %M1", "AND %M2", ")", "ST %Q0.1"]),
    ([c("%I0.0"), out("%Q0.4"), out("%M3", "SET"), out("%M4", "RST"), out("%M5", "OUTN")],
     ["LD %I0.0", "ST %Q0.4", "S %M3", "R %M4", "STN %M5"]),
    ([c("%I0.0", "FE"), c("%M1", "NC"), out("%Q0.4", "SET")], ["LDF %I0.0", "ANDN %M1", "S %Q0.4"]),
    ([c("%I0.0"), c("%I0.1"), {"kind": "TOF", "args": ["%TM1", "5", "100ms"]}],
     ["BLK %TM1", "LD %I0.0", "AND %I0.1", "IN", "END_BLK"]),
    ([c("%I0.3"), {"kind": "CTU", "args": ["%C1", "10"]}], ["BLK %C1", "LD %I0.3", "CU", "END_BLK"]),
])
def test_il_forms(elements, il):
    rung = {"elements": elements}
    assert not codec.validate([rung])
    assert codec.rung_il(rung) == il


@pytest.mark.parametrize("rung, fragment", [
    ({"elements": [c("%I0.0")]}, "at least one contact"),
    ({"elements": [out("%Q0.0")]}, "at least one contact"),
    ({"elements": [c("%I0.0"), out("%I0.1")]}, "cannot be written"),
    ({"elements": [c("%I0.0"), out("%TM0.Q")]}, "status bit"),
    ({"elements": [c("%I0.8"), out("%Q0.0")]}, "%I0.0 to %I0.7"),
    ({"elements": [c("%I0.0"), out("%Q0.8")]}, "%Q0.0 to %Q0.7"),
    ({"elements": [c("%M512"), out("%Q0.0")]}, "%M0 to %M511"),
    ({"elements": [c("%MW0"), out("%Q0.0")]}, "not an M221 bit address"),
    ({"elements": [c("%TM0"), out("%Q0.0")]}, "function block"),
    ({"elements": [c("X0"), out("%Q0.0")]}, "not an M221 bit address"),
    ({"elements": [c("%I0.0"), {"kind": "TON", "args": ["%C0", "3"]}]}, "timer like %TM0"),
    ({"elements": [c("%I0.0"), {"kind": "TON", "args": ["%TM0", "0"]}]}, "1..65535"),
    ({"elements": [c("%I0.0"), {"kind": "TON", "args": ["%TM0", "3", "2s"]}]}, "time base"),
    ({"elements": [c("%I0.0"), {"kind": "CTU", "args": ["%TM0", "3"]}]}, "counter like %C0"),
    ({"elements": [c("%I0.0"), {"kind": "CTU", "args": ["%C0", "abc"]}]}, "1..65535"),
    ({"elements": [c("%I0.0"), {"kind": "TON", "args": ["%TM0", "3"]}, out("%Q0.0")]}, "only output"),
    ({"elements": [out("%Q0.0"), c("%I0.0"), out("%Q0.1")]}, "start with a contact"),
    ({"elements": [{"branch": [[c("%I0.0")]]}, out("%Q0.0")]}, "two legs"),
    ({"elements": [{"branch": [[c("%I0.0")], [out("%Q0.1")]]}, out("%Q0.0")]}, "not inside a branch"),
    ({"elements": [c("%I0.0", note="a\nb"), out("%Q0.0")]}, "single-line"),
    ({"elements": [{"kind": "MOVE", "args": []}, out("%Q0.0")]}, "unknown element"),
])
def test_validate_rejects(rung, fragment):
    messages = [f.message for f in codec.validate([rung])]
    assert any(fragment in m for m in messages), messages


def test_validate_rejects_reused_blocks_and_bad_symbols():
    timer = {"elements": [c("%I0.0"), {"kind": "TON", "args": ["%TM0", "3"]}]}
    assert any("already used" in f.message for f in codec.validate([timer, timer]))
    assert any("letters" in f.message for f in codec.validate([timer], {"%I0.0": "1BAD"}))
    assert any("used for both" in f.message for f in codec.validate([timer], {"%I0.0": "A", "%I0.1": "a"}))
    assert any("must be %I0.x" in f.message for f in codec.validate([timer], {"%S0": "X"}))


def test_limits_come_from_the_project():
    limits = codec.limits_of(codec.parse(codec.read_text(TEMPLATE)))
    assert (limits.inputs, limits.outputs, limits.memory_bits, limits.timers, limits.counters) == (8, 8, 512, 255, 255)


def test_template_has_no_vendor_text_or_local_path():
    text = codec.read_text(TEMPLATE)
    root = codec.parse(text)
    assert all(not (e.text or "").strip() for e in root.iter("Comment"))
    assert root.findtext("Name") == "Project" and not root.findtext("FullName")
    assert "KERJA" not in text


def test_write_read_back(tmp_path):
    target = tmp_path / "conveyor.smbp"
    codec.write_project(target, TEMPLATE, CONVEYOR_RUNGS, SYMBOLS)
    raw = target.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf<?xml") and raw.count(b"\n") == raw.count(b"\r\n")
    assert b'xmlns:xsd="http://www.w3.org/2001/XMLSchema"' in raw[:400]
    project = codec.read_project(target)
    assert project["name"] == "conveyor" and project["cpu"] == "TM221M16R/G"
    rungs = project["pous"][0]["rungs"]
    assert [r["il"] for r in rungs] == EXPECTED_CONVEYOR_IL
    assert [r["name"] for r in rungs] == [r["name"] for r in CONVEYOR_RUNGS]
    assert not any(r["ladder"] for r in rungs)
    assert project["timers"] == [{"address": "%TM0", "type": "TON", "preset": 3, "base": "1s"}]
    assert project["counters"] == [{"address": "%C0", "preset": 10}]
    assert project["symbols"] == SYMBOLS
    assert project["comments"]["%Q0.1"] == "Warning horn" and project["comments"]["%C0"] == "Products per batch"
    assert codec.compare(target, CONVEYOR_RUNGS)["il_matches"]


def test_xml_member_order_matches_machine_expert(tmp_path):
    target = tmp_path / "c.smbp"
    codec.write_project(target, TEMPLATE, CONVEYOR_RUNGS, SYMBOLS)
    root = codec.parse(codec.read_text(target))
    timer = root.find("SoftwareConfiguration/Timers/TimerTM")
    assert [e.tag for e in timer] == ["Address", "Index", "Symbol", "Comment", "Preset", "Base"]
    inputs = root.findall("HardwareConfiguration/Plc/Cpu/DigitalInputs/DiscretInput")
    assert [e.tag for e in inputs[0]] == ["Address", "Index", "Symbol", "Comment", "DIFiltering", "DILatch"]
    assert [e.findtext("Address") for e in inputs] == [f"%I0.{n}" for n in range(8)]
    bits = root.findall("SoftwareConfiguration/MemoryBits/MemoryBit")
    assert [(e.findtext("Address"), e.findtext("Symbol")) for e in bits] == [("%M0", "RUN")]
    rung = root.find("SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity")
    assert [e.tag for e in rung] == ["LadderElements", "InstructionLines", "Name", "MainComment", "Label", "IsLadderSelected"]


def test_rewrite_is_stable(tmp_path):
    first, second = tmp_path / "a.smbp", tmp_path / "b.smbp"
    codec.write_project(first, TEMPLATE, CONVEYOR_RUNGS, SYMBOLS, target=tmp_path / "x.smbp")
    codec.write_project(second, first, CONVEYOR_RUNGS, SYMBOLS, target=tmp_path / "x.smbp")
    assert first.read_bytes() == second.read_bytes()


def test_template_round_trips_byte_for_byte(tmp_path):
    original = codec.read_text(TEMPLATE)
    assert codec.encode(codec.parse(original), original)[3:].decode("utf-8") == original


def test_reads_tool_saved_ladder_rung(tmp_path):
    # Machine Expert pads operators and keeps LadderElements after LD conversion
    text = codec.read_text(TEMPLATE)
    root = codec.parse(text)
    rung = root.find("SoftwareConfiguration/Pous/ProgramOrganizationUnits/Rungs/RungEntity")
    ET.SubElement(rung.find("LadderElements"), "LadderEntity")
    rung.find("IsLadderSelected").text = "true"
    rung.find("InstructionLines/InstructionLineEntity/InstructionLine").text = "LD    %I0.0"
    target = tmp_path / "t.smbp"
    target.write_bytes(codec.encode(root, text))
    read = codec.read_project(target)["pous"][0]["rungs"][0]
    assert read["il"] == ["LD %I0.0"] and read["ladder"] is True


def test_rejects_non_project(tmp_path):
    bad = tmp_path / "x.smbp"
    bad.write_text("<a/>")
    with pytest.raises(codec.FormatError):
        codec.read_project(bad)


def test_server_tools(tmp_path):
    names = {t["name"] for t in _tools()}
    assert names == {"list_templates", "instructions", "new_project", "validate", "write_program", "read_program", "compile"}
    assert not any(n.startswith("schneider_") for n in names)
    read_only = Server(gui_python=None, exe=None, allow_write=False)
    with pytest.raises(PermissionError):
        read_only.call("new_project", {"path": str(tmp_path / "p.smbp")})
    server = Server(gui_python=None, exe=None, allow_write=True)
    assert server.call("list_templates", {})["templates"] == ["TM221M16R"]
    target = tmp_path / "p.smbp"
    with pytest.raises(ValueError):
        server.call("new_project", {"path": str(tmp_path / "p.plc")})
    assert server.call("new_project", {"path": str(target)})["ok"]
    assert codec.read_project(target)["name"] == "p"
    with pytest.raises(FileExistsError):
        server.call("new_project", {"path": str(target)})
    bad = server.call("write_program", {"path": str(target), "rungs": [{"elements": [c("%I0.9"), out("%Q0.0")]}]})
    assert bad["written"] is False and "%I0.0 to %I0.7" in bad["findings"][0]["message"]
    ok = server.call("write_program", {"path": str(target), "rungs": CONVEYOR_RUNGS, "symbols": SYMBOLS})
    assert ok["written"] and ok["il_matches"] and Path(ok["backup"]).exists()
    assert not (tmp_path / "p.smbp.tmp").exists()
    assert server.call("validate", {"rungs": CONVEYOR_RUNGS, "path": str(target)})["expected_il"] == EXPECTED_CONVEYOR_IL
    assert server.call("read_program", {"path": str(target)})["pous"][0]["rungs"][4]["il"][0] == "BLK %C0"
    with pytest.raises(RuntimeError):
        server.call("compile", {"path": str(target)})


def test_stdio_protocol():
    import subprocess
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "validate", "arguments": {"rungs": CONVEYOR_RUNGS}}},
                {"jsonrpc": "2.0", "id": 4, "method": "nope"}]
    done = subprocess.run([sys.executable, "-m", "schneider_mcp"], cwd=Path(__file__).resolve().parents[1],
                          input="".join(json.dumps(r) + "\n" for r in requests), capture_output=True,
                          text=True, encoding="utf-8", timeout=60)
    replies = [json.loads(line) for line in done.stdout.splitlines()]
    assert [r["id"] for r in replies] == [1, 2, 3, 4]
    assert replies[0]["result"]["serverInfo"]["name"] == "schneider-mcp"
    assert len(replies[1]["result"]["tools"]) == 7
    payload = json.loads(replies[2]["result"]["content"][0]["text"])
    assert payload["ok"] and payload["expected_il"] == EXPECTED_CONVEYOR_IL
    assert replies[3]["error"]["code"] == -32601
