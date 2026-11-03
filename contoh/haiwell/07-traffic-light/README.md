# 07 — Four-approach traffic light with pedestrian phase

Target: **AT16S0T/P**. Tool: **Haiwell Happy V2.2.13.240603**. Created through the existing MCP backend, not manually drawn.

## Behavior

Eight phases: all red 2 s, north/south green 10 s, north/south yellow 3 s, all red 2 s, east/west green 10 s, east/west yellow 3 s, all red 2 s, pedestrian green 5 s, then repeat. The pedestrian pair serves one crossing while every vehicle approach is red. Each approach has its own red/yellow/green output command. No pedestrian push-button demand is modeled. Transition conditions are captured before phase writes; overlapping phase bits suppress every green/yellow command. Start from cleared, non-retained example state. This has not been verified across warm restart, power failure or retentive-state restoration.

The signal map uses fourteen logical/internal lamp commands, not a fourteen-physical-output claim. Add and independently verify a suitable I/O configuration before wiring lamps.

## Files and reuse

- [request.json](request.json): complete reusable MCP input (52 main rungs).
- [Native project](native/Case07.gpc): original agent-authored project; use your own licensed engineering software. Compiler caches, vendor libraries and user profiles are not included.
- [signals.csv](signals.csv): read-only signal contract for inspection, HMI-AI or content preparation; no live binding or HMI writer is implied.
- [native-evidence.json](native-evidence.json): actual sanitized native receipts, including limitations and any failed/recovered path.
- [source-files.json](source-files.json): SHA-256 pins for the request, native artifact, signals and evidence.

Give the connected agent this instruction in a fresh scratch workspace:

> Call `haiwell_validate` with request.json, `haiwell_new_project(path, template="AT16S0T")`, then `haiwell_write_ladder` with the request and the same fresh path. Call `haiwell_compile(path)` and `haiwell_export_il(path)`. Close/reopen the saved project without accepting unrelated edits and compare the complete exported IL. Set the router backend `timeout_s` to 1200 for the 52-rung case; `timeout` is not the configuration key. Do not use the desktop while the owned writer is typing. A lost reply is not permission to start a second writer: determine whether the original owned process is still active first. Never activate a runtime, connect/download/upload to a PLC, force values, install software or overwrite the supplied example.

## Evidence boundary

Native build: 0 errors / 0 warnings. Saved native ladder was independently read back. See the receipt for the exact comparison method; a compiler pass is not a behavioral simulation.

- The original router reply timed out under a misnamed local timeout setting. The owned writer finished; cold reopen, full saved IL comparison and native compile passed. Use timeout_s: 1200, not timeout.
- Fourteen lamp commands are logical variables/internal relays; this is not a verified fourteen-physical-output configuration.

**Not tested:** vendor simulator execution, Factory I/O, physical PLCs, sensor wiring, physical output polarity, stopping time or functional safety. EStopHealthy/GuardHealthy are ordinary status signals, never substitutes for independent safety hardware. Traffic logic is educational, not a certified public-road controller. No new video/GIF is claimed for this case.

See the [cross-vendor catalog](../../README.md) for available and unchecked topics and the shared test specification.
