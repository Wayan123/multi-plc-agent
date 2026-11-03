# 07 — Four-approach traffic light with pedestrian phase

Target: **Mega V3**. Tool: **Outseal Studio V3.6 Beta5**. Created through the existing MCP backend, not manually drawn.

## Behavior

Eight phases: all red 2 s, north/south green 10 s, north/south yellow 3 s, all red 2 s, east/west green 10 s, east/west yellow 3 s, all red 2 s, pedestrian green 5 s, then repeat. The pedestrian pair serves one crossing while every vehicle approach is red. Each approach has its own red/yellow/green output command. No pedestrian push-button demand is modeled. Transition conditions are captured before phase writes; overlapping phase bits suppress every green/yellow command. Start from cleared, non-retained example state. This has not been verified across warm restart, power failure or retentive-state restoration.

The Mega V3 profile provides 16 digital outputs; this case uses fourteen distinct R.1–R.14 commands. Physical wiring and hardware operation are untested.

## Files and reuse

- [request.json](request.json): complete reusable MCP input (52 main rungs).
- [Native project](native/Case07.plc): original agent-authored project; use your own licensed engineering software. Compiler caches, vendor libraries and user profiles are not included.
- [signals.csv](signals.csv): read-only signal contract for inspection, HMI-AI or content preparation; no live binding or HMI writer is implied.
- [native-evidence.json](native-evidence.json): actual sanitized native receipts, including limitations and any failed/recovered path.
- [source-files.json](source-files.json): SHA-256 pins for the request, native artifact, signals and evidence.

Give the connected agent this instruction in a fresh scratch workspace:

> Call `outseal_validate` with request.json, then `outseal_write_project` with the same object plus a fresh scratch `path`. Call `outseal_compile(path)` and `outseal_read_project(path)`. Compare board, initial and main instructions, aliases and timer presets; do not accept a missing native count. The recorded pass used an explicitly owned, UIA-ready Outseal host after a cold-start lookup failure. Do not attach to or overwrite a personal project. Never activate a runtime, connect/download/upload to a PLC, force values, install software or overwrite the supplied example.

## Evidence boundary

Native grammar/test error count: 0. A separate warning count is not exposed by this driver. Saved native ladder was independently read back. See the receipt for the exact comparison method; a compiler pass is not a behavioral simulation.

- Native Test passed in an explicitly owned prestarted UIA-ready host. A first cold-start lookup failed; cold-start reliability was not fixed or established.
- A fresh compiler HEX was observed; it was not uploaded.

**Not tested:** vendor simulator execution, Factory I/O, physical PLCs, sensor wiring, physical output polarity, stopping time or functional safety. EStopHealthy/GuardHealthy are ordinary status signals, never substitutes for independent safety hardware. Traffic logic is educational, not a certified public-road controller. No new video/GIF is claimed for this case.

See the [cross-vendor catalog](../../README.md) for available and unchecked topics and the shared test specification.
