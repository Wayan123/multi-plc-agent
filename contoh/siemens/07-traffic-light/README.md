# 07 — Four-approach traffic light with pedestrian phase

Target: **Siemens CPU 1212C DC/DC/DC**, TIA Portal **V20**. Created through TIA MCP in an isolated owned project.

## Behavior and limits

The [shared catalog](../../README.md#shared-behavior-specification) defines all timing, permissive and scan-transition behavior. This example contains 44 genuine boolean LAD networks plus eight SCL TON calls. State07 holds fourteen distinct logical lamp commands; the six-DO CPU is not claimed to drive fourteen physical lamps. All phase/initialization bits must start FALSE and non-retained.

## Files

DataAndTimers.scl, CallCase.scl, Main.s7dcl and the LAD FC documents are the complete original import source. The helper is SCL; this is not an all-LAD implementation.

- [specification.json](specification.json): original case contract.
- [signals.csv](signals.csv): read-only inspection/HMI contract, not live HMI integration or permission to write.
- [native-readback/Main.s7dcl](native-readback/Main.s7dcl): actual vendor export proving OB1's call after reopening.
- [native-evidence.json](native-evidence.json): sanitized actual imports, compiler and saved readback results.
- [source-files.json](source-files.json): SHA-256 pins.

## Recreate through MCP

1. Bootstrap TIA MCP, connect to a new isolated owned headless instance, and create a fresh project. Add CPU `6ES7212-1AE40-0XB0`, catalog firmware **V4.7**; discover the actual software path with GetProjectTree. The recorded path was PLC_1.
2. Import DataAndTimers.scl with ImportPlcExternalSource, then GenerateBlocksFromExternalSource. This creates State07 and Timers07.
3. Import Logic07 from the supplied S7DCL files with ImportFromDocuments. Do not convert the ladder into hand-written FlgNet XML.
4. CreateInstanceDB for Timers07, named Timers07_DB. Import CallCase.scl and generate its block.
5. Import Main.s7dcl with importOption=Override to replace only the fresh project's default Main. Main calls CallCase07; do not leave it uncalled.
6. CompileAndDiagnosePlc, SaveProject, CloseProject, reopen that exact saved .ap20, rediscover the software path, and compile again. Read the LAD FCs and timer/cycle with DescribeBlockLogic; export Main with ExportAsDocuments to independently verify the OB1 call. The current reader incorrectly labels some FC-call-only LAD networks as empty, so its summary is not sufficient.

Use supplied UTF-8 BOM S7DCL unchanged; ASCII-only SCL is UTF-8 without BOM. V20's accepted metadata here is S7_Language="LAD". Do not add the rejected S7_Version SD annotation or NETWORK-line comments from an untested template. Never overwrite a personal project, go online, download, force values or change software installations.

## Actual evidence

Fresh-open software compile: **0 errors / 0 warnings**. This is not a successful hardware-configuration compile or runtime test. The generated native compiler aliases for absolute I/O can differ from the input source; saved readable cycle evidence retains them.

**Not proved:** vendor simulator behavior, Factory I/O, physical PLCs, analog electrical calibration, real I/O polarity, safety or a physical sensor. A native compiler pass and code readback are not a simulation trace. No new GIF/video is claimed for this example.
