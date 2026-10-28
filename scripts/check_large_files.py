"""Fail if a tracked file is a video or larger than the limit (run in CI and before a release).

    python scripts/check_large_files.py [--max-mb 2]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

VIDEO = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--max-mb", type=float, default=2.0)
    args = parser.parse_args(argv)
    root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())
    files = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, check=True).stdout.split(b"\0")
    limit = int(args.max_mb * 1024 * 1024)
    bad = []
    for raw in filter(None, files):
        path = root / raw.decode("utf-8")
        if not path.is_file():
            continue
        size = path.stat().st_size
        if path.suffix.lower() in VIDEO:
            bad.append(f"{raw.decode()}: video files belong in the shared Drive folder (docs/media.md)")
        elif size > limit:
            bad.append(f"{raw.decode()}: {size / 1048576:.1f} MB exceeds {args.max_mb} MB")
    for line in bad:
        print(line)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
