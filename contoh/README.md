# PLC teaching examples

These are original examples authored through the existing PLC MCP backends. The checked entries below have actual vendor compilation and saved native readback evidence. **Checked does not mean simulated, commissioned, safety-certified or tested on a physical PLC.** Each example carries English instructions, a read-only signal map and source/evidence SHA-256 pins.

The user-approved scope is capability-adapted: do not invent four AI/two AO, fourteen physical outputs, a second CPU model or a working Modbus driver to fill a table. Empty/unchecked cells are deliberate, not hidden implementations.

## Available catalog

The original [seven Omron CX-Programmer examples](omron/README.md) remain available and unchanged, including their separately qualified analog, scaling and XY-MD02 cases.

| Backend / offline target | 01 Interlock + horn | 02 Start/stop + horn | 03 Four AI / two AO | 04 Analog scaling | 05 XY-MD02 | 06 Alternative XY-MD02 | 07 Traffic + pedestrian |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CPU 1212C DC/DC/DC (siemens) | [x] [Example 01](siemens/01-digital-interlock/) | [x] [Example 02](siemens/02-digital-start-stop/) | [x] [Example 03](siemens/03-analog-io/) | [x] [Example 04](siemens/04-analog-scaling/) | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](siemens/07-traffic-light/) |
| Outseal Nano V5 / Mega V3 (outseal) | [x] [Example 01](outseal/01-digital-interlock/) | [x] [Example 02](outseal/02-digital-start-stop/) | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](outseal/07-traffic-light/) |
| AT16S0T/P (haiwell) | [x] [Example 01](haiwell/01-digital-interlock/) | [x] [Example 02](haiwell/02-digital-start-stop/) | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](haiwell/07-traffic-light/) |
| DVP-SS2 (delta) | [x] [Example 01](delta/01-digital-interlock/) | [x] [Example 02](delta/02-digital-start-stop/) | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](delta/07-traffic-light/) |
| TM221M16R/G (schneider) | [x] [Example 01](schneider/01-digital-interlock/) | [x] [Example 02](schneider/02-digital-start-stop/) | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](schneider/07-traffic-light/) |
| CODESYS Control Win V3 x64 (codesys) | [x] [Example 01](codesys/01-digital-interlock/) | [x] [Example 02](codesys/02-digital-start-stop/) | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](codesys/07-traffic-light/) |
| TwinCAT RT (x64) (beckhoff) | [x] [Example 01](beckhoff/01-digital-interlock/) | [x] [Example 02](beckhoff/02-digital-start-stop/) | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [ ] Not implemented | [x] [Example 07](beckhoff/07-traffic-light/) |

**23 new native-accepted cases:** three digital/traffic cases on seven backends, plus Siemens analog I/O and scaling. Case 02 is a different behavior specification, not a claim of a distinct analog-equipped CPU on every backend.

### Unchecked topics and concrete prerequisites

- [ ] **XY-MD02 cases 05 and 06 on the new target set.** None of the six in-repository backend dialects used here exposes a verified serial Modbus master transaction for this sensor. For Siemens, a real RS-485 module/port configuration, installed native Modbus FB/interface, request-buffer ownership and timeout/error/stale-data contract still need native integration and independent validation. The presence of an RS-485 port or successful boolean-LD build is not proof of that integration. Use the existing [Omron Modbus examples](omron/README.md), not a renamed or mocked serial driver.
- [ ] **Four AI/two AO on Outseal.** The verified Nano/Mega profiles expose two analog inputs, not the requested four-AI/two-AO combination. This does not assert that every future Outseal variant is incapable of analog expansion.
- [ ] **Analog/scaling on Haiwell, Delta SS2 and Schneider M221 in this catalog.** Existing example dialects/fixtures do not provide a verified complete four-AI/two-AO channel configuration and analog instruction path. Select suitable modules/CPU and verify native instructions and data representation first.
- [ ] **Analog/scaling on CODESYS and TwinCAT in this catalog.** Current targets are logical software-PLC fixtures; physical terminal/device mapping, analog representation and quality bits are not configured. The CPU/runtime name alone does not establish analog I/O support.
- [ ] **Sysmac examples.** Actual case 01 XML import, native build (0 errors / 0 warnings) and saved five-rung comparison passed, but the saved task configuration had no assigned program. Also, the existing project-creation combo lookup failed before an exact native UIA model selection was used. No runnable Sysmac case is published here until native task assignment and reopen verification are complete; the existing backend remains available for its previously documented scope.
- [ ] **Mitsubishi variants in this catalog.** The existing conveyor demonstration is not evidence that these new teaching cases were compiled/read back in a fresh GX Works2 fixture. No new support claim is inferred from it.
- [ ] **Delta SV3/DIADesigner and Beckhoff CX7000.** Delta cases use WPLSoft DVP-SS2; Beckhoff cases use TwinCAT RT x64. Previously unverified target families remain unchecked.

## Conveyor process-simulation pilot

The [Beckhoff + Open Industry conveyor pilot](beckhoff/02-oip-conveyor/) adds a separate measured example: eight native LD rungs with save/reopen, matching independent export and 0 native errors / 0 warnings. The same nine scenarios / 54 checks passed on OIP IEC/Jolt, real OpenPLC v4.3.2 over Modbus TCP and licensed native Beckhoff Usermode Runtime 1.27.1 over ADS. Its MCP CLI recreates the scene and rejects an E-stop-interlock mutant in a separate internal-simulation project. A held-photoeye restart regression exposed and corrected duplicate counting in the new pilot.

The GIF shows **OIP internal IEC/Jolt execution**, not a native-runtime recording. OpenPLC and Beckhoff execution are evidenced separately by transport, tag and physical-cargo traces. The first native transfer smoke missed a timing deadline; a later complete run passed with unchanged controller/task/assertions, so no deterministic usermode timing is promised. ADS runner shutdown was independently red/green tested to clear active commands and reset the counter. Physical I/O, CX7000/ARM and hardware remain unverified. This pilot is distinct from the 23 capability-adapted teaching cases above, whose evidence levels are unchanged.

## Shared behavior specification

### 01 and 02: start/stop and a three-second horn

- Begin with cleared non-retained example state. A StartPB held at initial startup must not start Motor.
- Release StartPB with every permissive healthy to arm the next start. A subsequent StartPB seals RunRequest.
- Horn sounds while RunRequest is true and its 3 s TON is incomplete; Motor is commanded only when the TON completes.
- StopHealthy or EStopHealthy FALSE drops RunRequest, Motor and Horn in the logic scan. Case 01 additionally requires GuardHealthy. Case 02 omits that guard input.
- Restoring a permissive while StartPB remains held must not restart. Release and press again. Status inputs are not safety-rated control functions.

### 07: fourteen independent lamp commands

Each of north, south, east and west has its own red, yellow and green command. A separate red/green pedestrian pair serves one crossing. North/south share timing, as do east/west, but the fourteen output instructions/signals are separate. This example cycles the pedestrian phase automatically; it does not implement a pedestrian push-button request.

| Phase | Nominal duration | Vehicle commands | Pedestrian |
| --- | --- | --- | --- |
| 0 | 2 s | All red | Red |
| 1 | 10 s | North/south green; east/west red | Red |
| 2 | 3 s | North/south yellow; east/west red | Red |
| 3 | 2 s | All red | Red |
| 4 | 10 s | East/west green; north/south red | Red |
| 5 | 3 s | East/west yellow; north/south red | Red |
| 6 | 2 s | All red | Red |
| 7 | 5 s | All red | Green |

All timer/hold/advance conditions are captured before phase bits change, avoiding a stale timer Q cascading through phases in one scan. Only a unique active phase can permit green/yellow; overlapping phases command all vehicle red and pedestrian red. This is not proof of recovery/liveness from corrupt state, physical all-red operation, power-loss behavior or stuck-output detection. Timer resolution and scan quantization differ by vendor.

The Mega V3 Outseal profile supplies fourteen distinct physical output addresses. The other traffic fixtures use fourteen internal/logical commands; they do not claim fourteen terminals on a smaller CPU. Begin with cleared non-retained state. **Educational use only; not a public-road controller or functional-safety design.**

### 03 and 04: Siemens numeric analog examples

CPU 1212C with SM1231 AI4 and SM1232 AQ2. Four signed INT input words, two independent signed output command words and separate input nominal-range flags. Enable FALSE forces both output words to zero. Case 04 uses DINT intermediates for raw -27648..27648 to engineering -1000..1000 and the inverse, with clamping and integer division toward zero. Raw numeric limits are an example contract; electrical channel range, sensor calibration, quality diagnostics and actuator energy must be independently verified.

| Check | Input | Expected numeric result |
| --- | --- | --- |
| Input lower endpoint | -27648 raw | -1000 EU |
| Input midpoint | 0 raw | 0 EU |
| Input upper endpoint | 27648 raw | 1000 EU |
| Input above nominal | 32767 raw | 1000 EU; InRange FALSE |
| Output negative endpoint | -1000 EU, enabled | -27648 raw |
| Output above command limit | 2000 EU, enabled | 27648 raw |
| Disabled output | Any command, disabled | 0 raw |

These are expected arithmetic values, **not measurements from a simulator or PLC**. The native Siemens source and actual saved readback are provided for independent review.

## Reproduce and verify

1. Read the selected example README and its limitations. Use your installed licensed vendor tool and a fresh scratch project; never overwrite the bundled original to try a change.
2. Configure only that backend in multi-plc-agent. Call list_plc_backends first; use the complete request.json or Siemens source documents, not a screenshot or a manually drawn substitute.
3. Validate, author through MCP, compile in the native tool, save/close/reopen and independently read back the actual stored ladder/declarations/task where applicable. Record failed and recovered steps separately.
4. Use signals.csv as a **read-only logical contract** for future HMI-AI/content-studio work. It neither creates an HMI nor establishes live signal correspondence.
5. Before equipment use, separately perform vendor-simulator behavior tests, then appropriately authorized hardware checks with independent safety hardware. Do not infer those from a compiler result.

Local regression command from the repository root:

```sh
python3 -m pytest tests/test_teaching_cases.py -q
```

The 35 digital tests interpret the lowered request scan/TON model to check held-start/rearm, interlock loss, phase progression, conflict inhibition and fourteen lamp commands across seven dialects (including unqualified Sysmac lowering). They are deterministic **model checks, not vendor simulator execution**. Siemens has independent native compile/readback evidence but is not run by that model interpreter.

The [generator](teaching_cases.py) produces original canonical digital cases and existing backend requests; the shared IEC LD codec remains unchanged. No runtime, HMI application, new third-party backend or fake Modbus response service was added. Existing Omron consumer pins remain unchanged. New videos/GIFs have not been recorded for these cases.
