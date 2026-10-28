"""A release must ship one consistent version: package, CLI and changelog agree."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multiplc import __version__  # noqa: E402


def test_changelog_has_a_section_for_the_current_version():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(rf"^## \[{re.escape(__version__)}\] - \d{{4}}-\d{{2}}-\d{{2}}$", text, re.M), \
        f"CHANGELOG.md needs a '## [{__version__}] - YYYY-MM-DD' section"
    assert re.search(rf"^\[{re.escape(__version__)}\]: ", text, re.M), f"CHANGELOG.md needs a [{__version__}] link"


def test_cli_reports_the_package_version():
    out = subprocess.run([sys.executable, "-m", "multiplc", "--config", "unused.json", "--version"],
                         cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert out.stdout.strip() == __version__
