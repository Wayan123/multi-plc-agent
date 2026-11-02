# CP1H-X40DT-D: motor with a three-second prestart horn

The canonical original LD source is in per-rung mnemonic form in `program.json`; native CXT/CXP artifacts are also included in `mcp/`. Target CPU: **CP1H, CPU X**; do not substitute CP1E. CPU X has no built-in process analog. A642/A643 are not substitutes for process AI.

## Purpose and design choices

Two options were considered: a `SET/RSET` latch or an `OUT` coil with a seal-in branch. **Seal-in `OUT` + StartArmed** was chosen so the request has a single writer and Stop priority is immediately visible. The Start button may be released after one press; the request remains latched. This is not a jog example requiring Start to be held.

- `0.00` Start: NO, ON when pressed.
- `0.01` Stop_OK: ON when the normal operating Stop circuit is healthy; OFF stops the request on that scan.
- `1.00` Permissive_OK: ON when process permission is present. This is not an emergency stop or safety guard.
- `100.00` horn, `101.00` motor command; sinking transistor outputs.
- `W0.00` request, `W0.01` Start arming, `TIM 0000 #0030` prestart (30 × 0.1 s), `T0000` completion contact.

The rung order is deliberate: calculate request → calculate arming → timer → horn → motor. Arming is cleared while the request is active. Stop/permissive/first-cycle are after the Start/seal-in branch, so they override both. Loss of Stop or permissive clears the request and resets the timer; restoration does not automatically start the motor. Start must be released when ready and pressed again. `A200.11` makes the first scan always OFF even if Start is held or the work bit was previously ON.

The horn is ON only while the request is ON and the timer has not finished. The motor is ON only while the request is ON and the timer has finished. The timer resets if the condition is lost; a new press restarts the **nominal three-second preset**, not the remaining time. Physical horn duration is not established by the offline model. The motor output is a command, not proof that the motor rotates or the contactor actually opens.

## Noncontiguous physical I/O allocation

| Type | Correct terminal ranges | Count |
|---|---|---:|
| DC inputs | CIO `0.00–0.11` and `1.00–1.11` | 24 |
| Sinking transistor outputs | CIO `100.00–100.07` and `101.00–101.07` | 16 |

Not inputs `0.00–0.23` or outputs `100.00–100.15`. Input bits 12–15 on CIO 0/1 are not terminals and are always cleared. All 40 terminals are listed in `signals.csv`; spare terminals are not written by the program. Expansion starts at input CIO 2 and output CIO 102. The name `stop_ok` denotes logical polarity, not a safety wiring claim.

## Files and usage

- `program.json`: explicit model/CPU, LD rungs, and original scan scenarios; each instruction list is one CX-Programmer rung.
- `signals.csv`: fixed columns `signal,address,type,unit,hmi_access,description`; the HMI only reads physical buttons/status and does not write I/O.
- `prompt.id.md`: complete prompt for generating the same example from requirements, without taking a vendor example.

From the repository root, the shared offline check can be run with `python3 contoh/omron/check.py`. The checker executes a subset of mnemonics from JSON; it is **not an Omron compiler, CX-Simulator, or a hardware test**. Each named scenario has fresh state, input memory persists until changed, and `A200.11` comes from the first scan; `dt_ms` is discrete model time. The model adds `dt_ms` when the timer executes active: at the test boundary of 2,900 ms the horn remains on, at 3,000 ms the motor is on. This is not a measurement of physical PLC scan accuracy.

The LD was written through the multi-plc-agent MCP router, read back identically, and compiled in **CX-Programmer 9.75, model CP1H X: 0 errors, 0 warnings**. The example's native CXT/CXP and compiler output are in `mcp/`. The text seed was made specifically for the CP1H X profile, supported by Omron model metadata and compiler output; it is not a renamed CP1E project. The initial session's File/New CX-Server failure was not fixed by changing the installation or clock; opening a CPU-matched text project succeeded. CX-Simulator and a physical PLC have not been tested.

## Included edge cases

1. First scan OFF, arming after Start is released, self-hold after the button is released.
2. Horn still ON at 2.9 s; motor turns ON only at 3.0 s, horn OFF.
3. Start and Stop together: Stop wins, including while the motor is running.
4. Start held from startup or when Stop is restored: no auto-start.
5. Permissive lost while the horn or motor is active: all commands OFF; restart repeats the delay.
6. Restoring permissive while Start remains held does not generate a new request.

Expectations are in `scenarios`, not claims of execution results. Integrated verification is run by the integration owner after all examples are available.

## Safety and evidence limits

No download, online operation, forcing, COM/USB/serial access, or hardware changes. The example does not address emergency stop, overload, guards, contactor feedback, or STO. These functions must be designed and validated by an authorized engineer using appropriate equipment. Restart inhibition here is ordinary operating software behavior only; **it is not a certified safety function**. The horn and three-second delay do not prove the machine area is safe.

## Primary sources by fact

- [W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §1-2 p.15 and §2-2-2 pp.52–53: X/XA types and 24 inputs/16 outputs; §4-2-2 p.153 (PDF187): noncontiguous CIO ranges and expansion start.
- [W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), Appendix C p.648 (PDF682): `A200.11` ON for one cycle after operation starts.
- [W451-E1-03](https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1), §3-5-1 pp.169–172 (PDF202–205): `TIM` uses a BCD preset and 0.1 s units, resetting when the condition is OFF. The seal-in and arming policy are original example designs, not copies of a manual program.

All JSON, CSV, and text were written originally for the repository; no manuals, vendor templates, or other licensed tool code were copied into this folder.
