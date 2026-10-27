"""Outseal backend: codec round-trip, validator and MCP tool behaviour.

The round-trip test uses real Outseal Studio files when OUTSEAL_SAMPLES points
to a folder of .plc files (for example the examples bundled with Outseal
Studio); otherwise it runs only on files generated here.
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from outseal_mcp import codec  # noqa: E402
from outseal_mcp.server import Server  # noqa: E402
from outseal_mcp.validate import validate  # noqa: E402

E, R = codec.Element, codec.Rung

CONVEYOR = {
    "name": "Conveyor", "board": "Nano V5",
    "main": [
        {"comment": "Run request", "elements": [
            {"branch": [[{"kind": "NO", "args": ["S.1"]}], [{"kind": "NO", "args": ["B.1"]}]]},
            {"kind": "NO", "args": ["S.2"]}, {"kind": "NC", "args": ["C.1.DN"]},
            {"kind": "OUT", "args": ["B.1"]}]},
        {"elements": [{"kind": "NO", "args": ["B.1"]}, {"kind": "TON", "args": ["T.1", "1000", "3"]}]},
        {"elements": [{"kind": "NO", "args": ["B.1"]}, {"kind": "NC", "args": ["T.1.DN"]}, {"kind": "OUT", "args": ["R.2"]}]},
        {"elements": [{"kind": "NO", "args": ["B.1"]}, {"kind": "NO", "args": ["T.1.DN"]}, {"kind": "OUT", "args": ["R.1"]}]},
    ],
    "aliases": {"S.1": "Start", "S.2": "Stop", "R.1": "Motor", "R.2": "Horn"},
}


def _samples():
    folder = os.environ.get("OUTSEAL_SAMPLES")
    return sorted(Path(folder).glob("*.plc")) if folder else []


@pytest.mark.parametrize("path", _samples(), ids=lambda p: p.name)
def test_shipped_files_round_trip_exactly(path):
    text = codec.read_text(path)
    assert codec.encode(codec.decode(text)) == text


def test_generated_file_reads_back_and_keeps_json(tmp_path):
    project = codec.Project.from_json({**CONVEYOR, "hardware": CONVEYOR["board"]})
    target = tmp_path / "c.plc"
    codec.write_project(target, project)
    assert target.read_bytes().startswith(codec.BANNER)
    back = codec.read_project(target)
    assert back.to_json() == project.to_json()
    assert back.main[0].elements[0].kind == "Branch" and len(back.main[0].elements[0].legs) == 2


def test_delimiter_characters_are_rejected():
    project = codec.Project("x", "Nano V5", [R([E("NO", ["S.1"], note="bad \u24C9")])])
    with pytest.raises(codec.FormatError):
        codec.encode(project)


@pytest.mark.parametrize("element,expected", [
    (E("OUT", ["R.9"]), "R.1 to R.8"),             # Nano has 8 outputs; Outseal Studio itself accepts R.99
    (E("OUT", ["S.1"]), "cannot be written"),
    (E("NO", ["I.1"]), "word register"),
    (E("NO", ["T.1"]), "status bit"),
    (E("TON", ["T.1", "1000", "abc"]), "preset"),
    (E("TON", ["T.1", "7", "3"]), "time base"),
    (E("MOVE", ["I.1"]), "unknown instruction"),
    (E("OUT", ["R.0"]), "start at 1"),
])
def test_validator_rejects(element, expected):
    rung = R([E("NO", ["S.1"]), element]) if element.kind not in ("NO",) else R([element, E("OUT", ["R.1"])])
    errors = [f.message for f in validate(codec.Project("x", "Nano V5", [rung])) if f.level == "error"]
    assert any(expected in m for m in errors), errors


def test_validator_accepts_conveyor_and_mega_ranges():
    nano = codec.Project.from_json({**CONVEYOR, "hardware": "Nano V5"})
    assert not [f for f in validate(nano) if f.level == "error"]
    mega = codec.Project("m", "Mega V3", [R([E("NO", ["S.16"]), E("OUT", ["R.16"])])])
    assert not [f for f in validate(mega) if f.level == "error"]


def test_rung_must_end_in_output_or_output_branch():
    no_out = codec.Project("x", "Nano V5", [R([E("NO", ["S.1"]), E("NO", ["S.2"])])])
    assert any("must end" in f.message for f in validate(no_out))
    branch_out = codec.Project("x", "Nano V5", [R([E("NO", ["S.1"]), E("Branch", legs=[
        [E("OUT", ["R.1"])], [E("RST", ["T.1"])]])])])
    assert not [f for f in validate(branch_out) if f.level == "error"]


def test_write_tool_refuses_invalid_and_existing_files(tmp_path):
    server = Server(gui_python=None, outseal_exe=None, allow_write=True)
    target = tmp_path / "c.plc"
    bad = {**CONVEYOR, "path": str(target), "main": [{"elements": [{"kind": "OUT", "args": ["R.99"]}]}]}
    result = server.call("write_project", bad)
    assert result["written"] is False and not target.exists()
    ok = server.call("write_project", {**CONVEYOR, "path": str(target)})
    assert ok["written"] and target.exists()
    with pytest.raises(FileExistsError):
        server.call("write_project", {**CONVEYOR, "path": str(target)})
    again = server.call("write_project", {**CONVEYOR, "path": str(target), "overwrite": True})
    assert again["backup"] and Path(again["backup"]).exists()
    assert server.call("read_project", {"path": str(target)})["aliases"]["R.1"] == "Motor"


def test_write_tool_is_disabled_without_allow_write(tmp_path):
    server = Server(gui_python=None, outseal_exe=None, allow_write=False)
    with pytest.raises(PermissionError):
        server.call("write_project", {**CONVEYOR, "path": str(tmp_path / "c.plc")})
    assert json.dumps(server.call("list_boards", {}))
