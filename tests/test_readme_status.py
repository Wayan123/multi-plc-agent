"""The README status checklist must match the verified support table, in both languages."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def status(name: str) -> tuple[list[str], list[str], int]:
    text = (ROOT / name).read_text(encoding="utf-8")
    section = text.split("### Status", 1)[1].split("\n### ", 1)[0]
    checked = re.findall(r"^- \[x\] (.+)$", section, re.M)
    unchecked = re.findall(r"^- \[ \] (.+)$", section, re.M)
    details = text.split("\n### ", 2)[2].split("\n## ", 1)[0]
    rows = [r for r in details.splitlines() if r.startswith("| ") and not r.startswith("| Vendor") and "---" not in r]
    verified = [r for r in rows if "none yet" not in r and "belum ada" not in r]
    return checked, unchecked, len(verified)


def test_checked_boxes_match_verified_rows_and_both_languages_agree():
    en, en_open, en_rows = status("README.md")
    idn, id_open, id_rows = status("README.id.md")
    assert len(en) == en_rows, "a checked box needs a verified row in the details table, and the other way round"
    assert len(idn) == id_rows
    assert en == idn, "README.md and README.id.md list different supported tools"
    assert len(en_open) == len(id_open)
    assert f"({len(en)} tools" in (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"({len(idn)} software" in (ROOT / "README.id.md").read_text(encoding="utf-8")
