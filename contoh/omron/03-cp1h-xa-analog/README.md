# CP1H XA: four mixed AI and two guarded AO

An original LD example connects built-in analog words to HMI publication with validity and nominal output commands. It is not an analog safety circuit or evidence of wiring/native simulation.

## CPU, digital map, and required fixed configuration

Exact target **CP1H-XA40DT-D**, device `CP1H`, CPU `XA`: 24 DC inputs at CIO `0.00–0.11` **and** `1.00–1.11`; 16 sinking transistor outputs at CIO `100.00–100.07` **and** `101.00–101.07`. These are not contiguous ranges `0.00–0.23`/`100.00–100.15`. The analog ladder does not use digital terminals. Model X has no built-in process AI/AO and must not replace XA.

Configure the following in **CX-Programmer → PLC Setup → Built-in AD/DA**; this is an engineering prerequisite, not a runtime instruction:

| Channel | CIO word | Use | Fixed range | Physical input switch | Averaging |
|---|---:|---|---|---|---|
| AI0 | 200 | Yes | 0–10 V | OFF = voltage | OFF |
| AI1 | 201 | Yes | 4–20 mA | ON = current | OFF |
| AI2 | 202 | Yes | 0–10 V | OFF = voltage | OFF |
| AI3 | 203 | Yes | 4–20 mA | ON = current | OFF |
| AO0 | 210 | Yes | 0–10 V | not applicable | not applicable |
| AO1 | 211 | Yes | 4–20 mA | not applicable | not applicable |

**Common resolution for all channels = 6000.** Process values are binary/two's-complement, not BCD. The vendor procedure requires PLC Setup transfer and power OFF/ON for changes to be read; these hardware steps are **not performed by the example**. Physical AO terminals are named VOUT1/IOUT1 for AO0 and VOUT2/IOUT2 for AO1. A642/A643 are adjuster/external settings, not these four AI.

Do not write A75–A78, the A600-series, or analog expansion constants to CIO102 as an XA initializer. Numbers 75–78 in Appendix G are **internal PLC Setup** addresses, not Auxiliary Area addresses. No rung in the example writes an A-word. Retain mode/hold settings according to the engineer's assessment; the program does not change A500.12.

## Readiness, faults, and validity

- `A434.04` is read as **ON=ready/initialization complete**, OFF=initializing. Initial conversion takes about 1.5 s; do not replace readiness with an assumed fixed delay.
- `A315.14` ON indicates a built-in analog I/O error; all AI are declared invalid.
- `A434.01`/`.03` reject open-circuit current channels AI1/AI3. An unlit flag does not prove that the AI0/AI2 0–10 V wiring is intact.
- All channels reject word `#8000` even if the open-circuit flag is not yet ON. This is not a process number −32768 to scale.
- `A200.11` makes all publications invalid and both AO raw 0 on the first scan, even if readiness is already ON.
- HMI copies D100–D103 are **cleared to 0 each scan before conditional copy**. Use the `analog_input_n` + `analog_valid_n` pair; zero with valid=false is not a measurement. Raw words 200–203 are for diagnosis, not automatically valid measurements.
- Original application policy: both outputs are permitted normal operation only when **all four AI are valid**, so an open circuit on either current channel also drives both AO low. This is a conservative tutorial choice, not mandatory device behavior. When validity returns, existing D200/D201 commands are automatically applied again, subject to clamping; there is no manual restart gate.

AI data are nominal 0..6000, extended −300..6300. In 4–20 mA mode **raw 0=4 mA**, raw 6000=20 mA; do not subtract 1200. Below 3.2 mA, open circuit produces #8000. Negative extended raw values remain signed; a validity flag indicates readiness/error, not a guarantee that the sensor is within nominal range.

## Output limits and safety

AO0 raw 0=0 V and raw 6000=10 V. AO1 raw 0=**4 mA, not 0 mA**; raw 6000=20 mA. The application clamps only to nominal 0..6000 and does not use electrical overrange capability. On startup/fault the program selects raw 0 through arbitration; there is **one final writer per physical AO** so later normal rungs cannot override low.

This low, including 4 mA, is not proof of a safe process state. Built-in system error/CPU error may force 0 V/0 mA depending on device conditions; some other fatal errors produce live zero 1 V/4 mA. This differs from program raw 0. Changing RUN/PROGRAM with A500.12 OFF clears output words; with hold ON the previous value may be retained. The program does not prove actuator position, wiring integrity, or actual electrical output. Emergency stop, safety interlocks, guards, overload, and energy isolation require separate safety design. No hardware/COM/USB/serial access, online operation/download/force, or installation was performed in this work.

## Design choices and memory space

Two options: several rungs writing AO directly for startup/fault/normal, or scratch arbitration followed by one final writer. **Scratch D210/D211 + one final MOV** was chosen; a normal rung cannot silently override startup/fault low. D200/D201 are signed 16-bit commands in raw counts. Default scratch 0, copy only when output permission is ON and command is 0..6000, saturate high when command >6000. Negative commands (including #8000) become 0 because comparators with suffix S are signed, not unsigned.

| Area | Use |
|---|---|
| CIO200–203 | Device AI0–3 read-only |
| D100–103 | AI0–3 publication; zero when invalid |
| W0.00–.03 | AI0–3 validity |
| W0.04 | All AI valid; normal command permission |
| D200/D201 | Signed 16-bit AO0/AO1 commands |
| D210/D211 | Final scratch clamp 0..6000 |
| CIO210/CIO211 | One final writer per channel |

There is no 1200 offset for 4–20 mA input: conversion in this mode already gives raw 0 at 4 mA. This example does not yet perform engineering-unit scaling; example 04 shows a 32-bit intermediate. The validity flag does not indicate command clamping: commands outside nominal range remain permitted but are saturated.

## Edge cases in JSON

- First scan even with ready=ON; readiness OFF for longer; only after ready ON does the copy become valid.
- Raw endpoints 0 and 6000 across all ranges, midpoint 3000; output 0/3000/6000.
- Commands −1, #8000, 6001, 6300, 32767: lower/upper signed clamp; extended inputs −300/6300 are not interpreted as unsigned.
- Built-in error or loss of readiness after nonzero values: all copies cleared and validity OFF, both AO raw 0.
- Separate AI1 and AI3 open circuits, and sentinel #8000 on each of the four AI; other channel validity remains visible, both AO raw 0 until all are valid again.

## Source format and verification path

`program.json` contains LD rungs as original mnemonic lists and scan scenarios. `signals.csv` has exactly the columns signal,address,type,unit,hmi_access,description. The HMI reads values+validity; only application command registers are marked read_write, not CIO/A-status. `prompt.id.md` is the complete reproduction prompt. This folder contains no manual/vendor template/third-party tool code.

From the repository root, run the shared checker `python3 contoh/omron/check.py` after integration is complete. This is a **limited offline mnemonic model**, not an Omron compiler or CX-Simulator; scenario expectations are not evidence of native simulation or physical values. Each scenario starts with fresh memory; inputs persist until changed; A200.11 is automatic on the first scan; negative memory numbers are written as unsigned 16-bit bit patterns (e.g. −300=65236, #8000=32768).

LD was written through multi-plc-agent MCP, read back identically, and **compiled in CX-Programmer 9.75 for model CP1H XA: 0 errors, 0 warnings**. CXT/CXP and compiler evidence are in `mcp/`; the original text seed uses the XA profile, not a CP1E template. File/New CX-Server initially failed, but opening a matching CPU text file succeeded without clock/installation changes. Analog PLC Setup settings have not been transferred and **physical voltage/current has not been tested**; CX-Simulator was not run.

## Primary sources by fact

- [W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §1-2 p.15; §2-2-2 pp.52–53; §4-2-2 p.153 (PDF187): CPU XA, 24DI/16DO and noncontiguous CIO map. §4-3 p.159 (PDF193): fixed analog allocation and hold/mode behavior.
- [W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §5-5 pp.326–331 (PDF360–365): binary conversion, 0–10 V/4–20 mA, raw 0=4 mA, extended −300..6300 and #8000/open circuit.
- [W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §5-5 pp.332–333 (PDF366–367), Appendix G pp.761–762 (PDF795–796): PLC Setup, common resolution 6000, voltage/current switch, Use/range/averaging, power-on settings; not an A-word initializer.
- [W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §5-5 pp.336–337 (PDF370–371): A434.04 ON=completed, initial delay, status and fault output; §11-2 p.614 (PDF648): A315.14; Appendix C p.648 (PDF682): A200.11.
- [W451-E1-03](https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1), §3-6-1 pp.211–214 (PDF244–247): comparator without S=unsigned, with S=signed; §3-7-1 p.247 (PDF280): MOV(021). Validity, clamp, and arbitration policy are original example designs, not copies of a manual program.
