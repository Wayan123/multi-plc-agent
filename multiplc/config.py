"""Backend registry loaded from a JSON config file."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .backend import BackendSpec

# Known vendors: tool-name prefix and tools never exposed by default.
# Denied tools act on a live PLC or delete project content. Users who
# need them can call the vendor server directly with its own approvals.
VENDOR_DEFAULTS: dict[str, dict[str, Any]] = {
    "mitsubishi": {
        "prefix": "mitsubishi_",
        "deny": [],
        "proxy_tools": [],
    },
    "siemens": {
        "prefix": "siemens_",
        "deny": [
            "DownloadToPlc", "GoOnline", "SetWatchTableModifyValue",
            "DeletePlcBlock", "DeletePlcTag", "DeletePlcTagTable", "DeletePlcType",
            "DeletePlcWatchTable", "DeletePlcExternalSource", "DeleteDevice",
            "DeleteExport", "ClearExports", "EnsureOpennessUserGroup", "Doctor",
        ],
        "proxy_tools": ["CallTool"],
    },
    "omron": {
        "prefix": "omron_",
        "deny": ["delete_rung"],
        "proxy_tools": [],
    },
    "outseal": {
        "prefix": "outseal_",
        "deny": [],
        "proxy_tools": [],
    },
    "haiwell": {
        "prefix": "haiwell_",
        "deny": [],
        "proxy_tools": [],
    },
}


class ConfigError(ValueError):
    pass


def _expand(value: str) -> str:
    return os.path.expandvars(os.path.expanduser(value))


def load_config(path: str | Path) -> list[BackendSpec]:
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigError(f"cannot read {path}: {error}") from error
    entries = data.get("backends")
    if not isinstance(entries, dict) or not entries:
        raise ConfigError(f"{path}: 'backends' must be a non-empty object")
    specs: list[BackendSpec] = []
    prefixes: set[str] = set()
    for name, entry in entries.items():
        if not isinstance(entry, dict):
            raise ConfigError(f"backend {name!r} must be an object")
        if entry.get("enabled", True) is False:
            continue
        vendor = entry.get("vendor")
        if vendor not in VENDOR_DEFAULTS:
            raise ConfigError(f"backend {name!r}: vendor must be one of {sorted(VENDOR_DEFAULTS)}")
        defaults = VENDOR_DEFAULTS[vendor]
        command = entry.get("command")
        if not isinstance(command, str) or not command:
            raise ConfigError(f"backend {name!r}: 'command' is required")
        prefix = entry.get("prefix", defaults["prefix"])
        if prefix in prefixes:
            raise ConfigError(f"backend {name!r}: prefix {prefix!r} is already used")
        prefixes.add(prefix)
        deny = set(defaults["deny"])
        deny |= set(entry.get("deny", []))
        deny -= set(entry.get("allow", []))
        specs.append(BackendSpec(
            name=name,
            prefix=prefix,
            vendor=vendor,
            software=str(entry.get("software", "")),
            command=_expand(command),
            args=tuple(_expand(str(arg)) for arg in entry.get("args", [])),
            cwd=_expand(entry["cwd"]) if entry.get("cwd") else None,
            env={str(k): _expand(str(v)) for k, v in entry.get("env", {}).items()},
            deny=frozenset(deny),
            proxy_tools=frozenset(entry.get("proxy_tools", defaults["proxy_tools"])),
            timeout_s=float(entry.get("timeout_s", 600)),
            start_timeout_s=float(entry.get("start_timeout_s", 180)),
        ))
    return specs
