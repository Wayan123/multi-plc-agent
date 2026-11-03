# 07 — Four-approach traffic light with pedestrian phase

Target: **CODESYS Control Win V3 x64**. Tool: **CODESYS V3.5 SP21**. Created through the existing MCP backend, not manually drawn.

## Behavior

Eight phases: all red 2 s, north/south green 10 s, north/south yellow 3 s, all red 2 s, east/west green 10 s, east/west yellow 3 s, all red 2 s, pedestrian green 5 s, then repeat. The pedestrian pair serves one crossing while every vehicle approach is red. Each approach has its own red/yellow/green output command. No pedestrian push-button demand is modeled. Transition conditions are captured before phase writes; overlapping phase bits suppress every green/yellow command. Start from cleared, non-retained example state. This has not been verified across warm restart, power failure or retentive-state restoration.

The signal map uses fourteen logical/internal lamp commands, not a fourteen-physical-output claim. Add and independently verify a suitable I/O configuration before wiring lamps.

## Files and reuse

- [request.json](request.json): complete reusable MCP input (52 main rungs).
- [Native project](native/Case07.project): original agent-authored project; use your own licensed engineering software. Compiler caches, vendor libraries and user profiles are not included.
- [signals.csv](signals.csv): read-only signal contract for inspection, HMI-AI or content preparation; no live binding or HMI writer is implied.
- [native-evidence.json](native-evidence.json): actual sanitized native receipts, including limitations and any failed/recovered path.
- [source-files.json](source-files.json): SHA-256 pins for the request, native artifact, signals and evidence.

Give the connected agent this instruction in a fresh scratch workspace:

> Call `codesys_validate` with request.json, then `codesys_write_ladder` with the same request, `pou="PLC_PRG"` and a fresh `.project` path. Call `codesys_build(path)` and `codesys_export_pou(path, pou="PLC_PRG", include_xml=true)` in fresh headless invocations. Require native error_count/warning_count and matching LD/declarations. The generated MainTask calls PLC_PRG. Do not log in or download to a runtime. Never activate a runtime, connect/download/upload to a PLC, force values, install software or overwrite the supplied example.

## Evidence boundary

Native build: 0 errors / 0 warnings. Saved native ladder was independently read back. See the receipt for the exact comparison method; a compiler pass is not a behavioral simulation.

- Fourteen lamp commands are logical variables/internal relays; this is not a verified fourteen-physical-output configuration.

**Not tested:** vendor simulator execution, Factory I/O, physical PLCs, sensor wiring, physical output polarity, stopping time or functional safety. EStopHealthy/GuardHealthy are ordinary status signals, never substitutes for independent safety hardware. Traffic logic is educational, not a certified public-road controller. No new video/GIF is claimed for this case.

See the [cross-vendor catalog](../../README.md) for available and unchecked topics and the shared test specification.
