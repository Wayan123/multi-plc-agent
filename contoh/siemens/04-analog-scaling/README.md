# 04 — Analog input and output scaling

Target: **Siemens CPU 1212C DC/DC/DC**, TIA Portal **V20**. Created through TIA MCP in an isolated owned project.

## Behavior and limits

Four raw INT input words are copied every scan, with separate nominal-range flags. Two independent command words are clamped and written to the analog outputs. Enabled is read from I0.0; FALSE forces both output words to zero. Input range flags do not constitute module health, wire-break detection or a safety function. Input scaling clamps raw values to -27648..27648, then computes (DINT(raw) * 1000) / 27648. Output scaling clamps DINT commands to -1000..1000, then computes (command * 27648) / 1000. DINT intermediates avoid 16-bit multiplication overflow. Integer division truncates toward zero; units are arbitrary engineering units, not measured temperature or a calibrated electrical unit. **Electrical range is not commissioned:** +/-27648 is the example numeric nominal domain. Verify/set each real channel's voltage/current measurement type, polarity and range before deriving physical units. Zero raw output is a numeric command, not a universal guarantee of zero actuator energy.

## Files

Analog.scl contains the original state DB and SCL data/scaling cycle; Main.s7dcl is the genuine LAD OB1 call. This is an LAD/SCL hybrid, not a claim that the arithmetic was manually entered as LD.

- [specification.json](specification.json): original case contract.
- [signals.csv](signals.csv): read-only inspection/HMI contract, not live HMI integration or permission to write.
- [native-readback/Main.s7dcl](native-readback/Main.s7dcl): actual vendor export proving OB1's call after reopening.
- [native-evidence.json](native-evidence.json): sanitized actual imports, compiler and saved readback results.
- [source-files.json](source-files.json): SHA-256 pins.

## Recreate through MCP

1. Bootstrap TIA MCP and use an isolated owned instance. Create a fresh project and add CPU `6ES7212-1AE40-0XB0`, explicit catalog firmware **V4.2**. Discover software and rack paths. V4.2 is an offline fixture choice, not identification of a physical CPU.
2. Query GetDevicePlugLocations for PLC_1/Rack_0. In the recorded fresh rack, positions 2 and 3 were free. Dry-run, then insert SM1231 AI4 `6ES7231-4HD32-0XB0` V2.1 at 2 and SM1232 AQ2 `6ES7232-4HB32-0XB0` V2.1 at 3 using PlugDeviceItem. Never retry an insert solely because that tool's post-write verifier says VerifyFailed: inspect the tree and actual I/O addresses first.
3. Independently read GetDeviceItemTree and GetDeviceItemIoAddresses on the discovered channel subitems. Recorded input start: 96; output start: 112. The source uses IW96/98/100/102 and QW112/114. If addresses differ, regenerate/review the source to match the actual offline configuration before importing; do not merely relabel signals.csv.
4. Import Analog.scl with ImportPlcExternalSource, then GenerateBlocksFromExternalSource. Import Main.s7dcl with Override in this fresh project; OB1 calls AnalogCycle04.
5. Compile hardware and software separately. Save/close/reopen the exact .ap20, compile again, read AnalogCycle04 and export Main's actual native S7DCL to verify its call.

Use supplied UTF-8 BOM S7DCL unchanged; ASCII-only SCL is UTF-8 without BOM. V20's accepted metadata here is S7_Language="LAD". Do not add the rejected S7_Version SD annotation or NETWORK-line comments from an untested template. Never overwrite a personal project, go online, download, force values or change software installations.

## Actual evidence

Fresh-open software compile: **0 errors / 0 warnings**. Hardware compile: **0 errors / 1 warning**, because the scratch CPU has no configured protection level. Do not deploy it unchanged. An initial V4.7 scratch hardware compile failed on confidential-configuration password/certificate prerequisites; that failed attempt is preserved in case 03 evidence. The passing engineering fixture explicitly uses V4.2, without changing installations or weakening a production controller.

**Not proved:** vendor simulator behavior, Factory I/O, physical PLCs, analog electrical calibration, real I/O polarity, safety or a physical sensor. A native compiler pass and code readback are not a simulation trace. No new GIF/video is claimed for this example.
