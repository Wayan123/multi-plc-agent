"""Check that the vendor pages behind multiplc/clients.py still describe the formats we write.

    python scripts/check_client_docs.py            # prints one line per client, exit 1 on drift
    python scripts/check_client_docs.py --markdown # the same as a Markdown report (used for the CI issue)

A page that can't be fetched or lost a marker string means the client's config format may have
changed. Re-read the page, update multiplc/clients.py and docs/clients.md, then bump 'checked'.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SOURCES = Path(__file__).resolve().parents[1] / "multiplc" / "client_sources.json"


def check(url: str, markers: list[str]) -> tuple[bool, str]:
    request = urllib.request.Request(url, headers={"User-Agent": "multi-plc-agent-docs-check"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            text = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError) as error:
        return False, f"fetch failed: {error}"
    missing = [m for m in markers if m not in text]
    return (not missing), ("ok" if not missing else "missing: " + ", ".join(missing))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(SOURCES.read_text(encoding="utf-8"))
    results = {key: check(src["url"], src["markers"]) for key, src in data["clients"].items()}
    failed = {k: v for k, v in results.items() if not v[0]}
    if args.markdown:
        print(f"Client documentation check (sources last reviewed {data['checked']}).\n")
        print("| Client | Page | Result |\n| --- | --- | --- |")
        for key, (_, detail) in results.items():
            print(f"| {key} | {data['clients'][key]['url']} | {detail} |")
        if failed:
            print("\nRe-read the failing pages, update `multiplc/clients.py` and `docs/clients.md`, "
                  "then set `checked` in `multiplc/client_sources.json`.")
    else:
        for key, (ok, detail) in results.items():
            print(f"{'ok  ' if ok else 'FAIL'} {key:15} {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
