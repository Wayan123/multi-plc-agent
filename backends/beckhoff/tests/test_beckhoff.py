"""Native-export fixtures come from real owned TwinCAT XAE 4026.27 runs.

These tests do not simulate the compiler. In particular, a successful build of
another program must not satisfy LD/declaration/task readback acceptance.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from backends.beckhoff.beckhoff_mcp.server import MARKER, Server, snapshot, verify_readback

FIXTURES = Path(__file__).with_name("fixtures")
REQUEST = json.loads((ROOT / "contoh/beckhoff/01-twincat-rt-x64-conveyor/request.json").read_text())
NATIVE = (FIXTURES / "conveyor-native.xml").read_text(encoding="utf-8-sig")


def test_actual_vendor_export_has_counter_reset_batch_inhibit_and_called_task():
    actual = verify_readback(NATIVE, **REQUEST)
    assert actual["logic_matches"] is True
    assert actual["declarations_match"] is True
    assert actual["task_bound"] is True
    assert actual["logic"][0]["logic"] == "(EStopHealthy AND NOT BatchCounter.Q AND RunReq AND StopNC) OR (EStopHealthy AND NOT BatchCounter.Q AND StartPB AND StopNC)"
    assert actual["logic"][4] == {"comment": "Count ten parts; independent reset", "kind": "CTU", "target": "BatchCounter", "logic": "Motor AND PartSensor", "params": {"PV": "10", "RESET": "CountReset"}}
    assert actual["declarations"]["StartDelay"] == {"type": "TON", "address": ""}
    assert actual["declarations"]["BatchCounter"] == {"type": "CTU", "address": ""}


def test_compile_accepted_different_native_program_is_not_accepted_as_the_conveyor():
    xml = (FIXTURES / "different-program-native.xml").read_text(encoding="utf-8-sig")
    actual = verify_readback(xml, **REQUEST)
    assert actual["logic"] == [{"comment": "Agent-authored native LD probe", "kind": "OUT", "target": "Lamp", "logic": "Start"}]
    assert actual["logic_matches"] is False
    assert actual["declarations_match"] is False
    assert actual["task_bound"] is True


def test_matching_diagram_without_a_task_call_is_not_accepted():
    root = ET.fromstring(NATIVE)
    for task in root.iter():
        if task.tag.rsplit("}", 1)[-1] == "task":
            for child in list(task):
                if child.tag.rsplit("}", 1)[-1] == "pouInstance":
                    task.remove(child)
    actual = verify_readback(ET.tostring(root, encoding="unicode"), **REQUEST)
    assert actual["logic_matches"] is True
    assert actual["declarations_match"] is True
    assert actual["task_bound"] is False


def test_native_timer_type_drift_is_not_hidden_by_matching_boolean_logic():
    root = ET.fromstring(NATIVE)
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] == "derived" and element.get("name") == "TON":
            element.set("name", "TOF")
    actual = verify_readback(ET.tostring(root, encoding="unicode"), **REQUEST)
    assert actual["logic_matches"] is True
    assert actual["declarations_match"] is False


def test_duplicate_native_main_is_ambiguous_and_rejected():
    root = ET.fromstring(NATIVE)
    pou = next(n for n in root.iter() if n.tag.rsplit("}", 1)[-1] == "pou" and n.get("name") == "MAIN")
    root.append(ET.fromstring(ET.tostring(pou)))
    with pytest.raises(ValueError):
        snapshot(ET.tostring(root, encoding="unicode"))


def test_writer_denies_before_creating_workspace_without_opt_in(tmp_path):
    workspace = tmp_path / "workspace"
    with pytest.raises(PermissionError):
        Server(workspace).call("write_ladder", {"path": "project/demo.sln", **REQUEST})
    assert workspace.exists() is False


def test_writer_cannot_escape_workspace_or_replace_unowned_data(tmp_path):
    workspace = tmp_path / "workspace"
    on = Server(workspace, True)
    with pytest.raises(PermissionError):
        on.call("write_ladder", {"path": "../../outside/demo.sln", **REQUEST})
    project = workspace / "project"
    project.mkdir(parents=True)
    source = project / "demo.sln"
    source.write_text("user-owned solution", encoding="utf-8")
    with pytest.raises(FileExistsError):
        on.call("write_ladder", {"path": str(source), "overwrite": True, **REQUEST})
    assert source.read_text() == "user-owned solution"
    assert not project.with_name("project.bak").exists()


def test_existing_backup_is_never_overwritten_or_used_as_a_retry_target(tmp_path):
    workspace = tmp_path / "workspace"
    project = workspace / "project"
    project.mkdir(parents=True)
    source = project / "demo.sln"
    source.write_text("current solution")
    (project / MARKER).write_text(json.dumps({"owner": "beckhoff-mcp", "solution": "demo.sln"}))
    backup = workspace / "project.bak"
    backup.mkdir()
    previous = backup / "important.txt"
    previous.write_text("earlier backup")
    with pytest.raises(FileExistsError):
        Server(workspace, True).call("write_ladder", {"path": str(source), "overwrite": True, **REQUEST})
    assert source.read_text() == "current solution"
    assert previous.read_text() == "earlier backup"
