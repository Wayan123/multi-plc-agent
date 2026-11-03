# 02 — Digital I/O: start/stop and warning horn

Target: **TM221M16R/G**. Tool: **EcoStruxure Machine Expert - Basic**. Created through the existing MCP backend, not manually drawn.

## Behavior

Release StartPB once with StopHealthy and EStopHealthy TRUE. A subsequent start seals RunRequest; Horn sounds during the three-second TON delay and Motor is commanded only after it expires. Losing any permissive drops the request and outputs; a held start cannot restart it until released. Case 02 deliberately omits the guard input; it does not invent a second CPU/analog model for this vendor.

Input TRUE means a healthy permissive. Address mapping is in signals.csv; named IEC variables are logical until real I/O is separately mapped.

## Files and reuse

- [request.json](request.json): complete reusable MCP input (5 main rungs).
- [Native project](native/Case02.smbp): original agent-authored project; use your own licensed engineering software. Compiler caches, vendor libraries and user profiles are not included.
- [signals.csv](signals.csv): read-only signal contract for inspection, HMI-AI or content preparation; no live binding or HMI writer is implied.
- [native-evidence.json](native-evidence.json): actual sanitized native receipts, including limitations and any failed/recovered path.
- [source-files.json](source-files.json): SHA-256 pins for the request, native artifact, signals and evidence.

Give the connected agent this instruction in a fresh scratch workspace:

> Call `schneider_new_project(path)`, `schneider_validate` with request.json, and `schneider_write_program` with the request and the fresh path. Call `schneider_compile(path, to_ladder=true, rungs=request.rungs)`, then `schneider_read_program(path)`. Require native No error status, saved LD conversion and full native saved-file IL matching. Keep the raw UI readback verdict separate: aliases need symbol resolution and the traffic editor virtualizes rows. Never activate a runtime, connect/download/upload to a PLC, force values, install software or overwrite the supplied example.

## Evidence boundary

Native grammar/test error count: 0. A separate warning count is not exposed by this driver. Saved native ladder was independently read back. See the receipt for the exact comparison method; a compiler pass is not a behavioral simulation.

- The raw UI-only IL match is false. Complete native saved-file IL matches the request. Digital UI aliases resolve through saved symbol mappings; traffic UI rows are virtualized/incomplete.

**Not tested:** vendor simulator execution, Factory I/O, physical PLCs, sensor wiring, physical output polarity, stopping time or functional safety. EStopHealthy/GuardHealthy are ordinary status signals, never substitutes for independent safety hardware. Traffic logic is educational, not a certified public-road controller. No new video/GIF is claimed for this case.

See the [cross-vendor catalog](../../README.md) for available and unchecked topics and the shared test specification.
