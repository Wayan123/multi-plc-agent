"""Command line entry: run the router over stdio, or check the backends once."""
from __future__ import annotations

import argparse
import io
import json
import sys

from . import __version__
from .config import ConfigError, load_config
from .router import Router, StdioServer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="multi-plc-agent", description=__doc__)
    parser.add_argument("--config", required=True, help="backends JSON file (see config.example.json)")
    parser.add_argument("--check", action="store_true",
                        help="start every backend, print status as JSON and exit")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    try:
        specs = load_config(args.config)
    except ConfigError as error:
        print(f"multi-plc-agent: {error}", file=sys.stderr)
        return 2
    router = Router(specs)
    if args.check:
        router.start({"name": "multi-plc-agent-check", "version": __version__})
        try:
            status = router.backend_status()
        finally:
            router.stop()
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if all(row["status"] == "running" for row in status["backends"]) else 1
    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
    StdioServer(router, stdin, stdout).serve()
    return 0


if __name__ == "__main__":
    sys.exit(main())
