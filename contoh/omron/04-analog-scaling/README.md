# Signed analog scaling with 32-bit intermediate

An original LD example for **CP1H-XA40DT-D**. AI0 raw 0..6000 is mapped to engineering **−1000..+1000 in 0.1 units** (−100.0..+100.0 units). A command of 0..1000 in 0.1 percent (0.0..100.0%) is mapped to raw AO 0..6000 for both outputs with different electrical modes. These engineering units are a tutorial choice, not vendor sensor calibration.

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
- Original application policy: both outputs are permitted normal operation only when **all four AI are valid**, so an open circuit on either current channel also drives both AO low. This is a conservative tutorial choice, not mandatory device behavior. When validity returns, the existing D200 command is automatically applied again, subject to clamping; there is no manual restart gate.

AI data are nominal 0..6000, extended −300..6300. In 4–20 mA mode **raw 0=4 mA**, raw 6000=20 mA; do not subtract 1200. Below 3.2 mA, open circuit produces #8000. Negative extended raw values remain signed; a validity flag indicates readiness/error, not a guarantee that the sensor is within nominal range.

## Output limits and safety

AO0 raw 0=0 V and raw 6000=10 V. AO1 raw 0=**4 mA, not 0 mA**; raw 6000=20 mA. The application clamps only to nominal 0..6000 and does not use electrical overrange capability. On startup/fault the program selects raw 0 through arbitration; there is **one final writer per physical AO** so later normal rungs cannot override low.

This low, including 4 mA, is not proof of a safe process state. Built-in system error/CPU error may force 0 V/0 mA depending on device conditions; some other fatal errors produce live zero 1 V/4 mA. This differs from program raw 0. Changing RUN/PROGRAM with A500.12 OFF clears output words; with hold ON the previous value may be retained. The program does not prove actuator position, wiring integrity, or actual electrical output. Emergency stop, safety interlocks, guards, overload, and energy isolation require separate safety design. No hardware/COM/USB/serial access, online operation/download/force, or installation was performed in this work.

## Two approaches and the choice

`SCL(194)` produces unsigned BCD; `SCL2(486)` uses magnitude BCD and sign Carry; `SCL3(487)` accepts BCD ΔX parameters and a signed one-word result. The selected alternative is **signed multiply 16×16 producing 32 bits, then 32-bit divide and 32-bit subtract**. This retains the engineering sign and full product without treating BCD scaling instructions as signed 32-bit binary.

`*L(421)` is unnecessary: its result is 64 bits and `/L(431)` reads only a 32-bit dividend. `MOVL 200 D100` is not sign-extension of AI0 either, because it would use AI1 as the high word. The example uses `MOV(021)` to copy AI and `*(420)` to produce signed 32-bit results.

## Formula, clamp, and actual footprint

1. Reject readiness/fault/first scan/#8000 before mathematics; valid AI0 is copied to D100.
2. Clamp **signed** D100 to D104=0..6000. Extended −300 becomes 0, 6300 becomes 6000. Comparators use `AND<S(312)`/`AND>S(322)`; without S negative values would be read as large unsigned values.
3. `*(420) D104 &2000 D110`: signed16×signed16, 32-bit product at D110 low/D111 high.
4. `MOVL(498) &6000 D170` sets the 32-bit divisor at D170 low/D171 high=0 every scan. Then `/L(431) D110 D170 D120`: quotient D120–121 and **remainder D122–123**.
5. `MOVL(498) &1000 D172` sets D172 low/D173 high=0, also every scan. `-L(411) D120 D172 D130` produces signed 32-bit engineering D130–131. Value −1000 has low #FC18/high #FFFF, not BCD.
6. Gate on all AI valid then clamp **signed** command D200 to D140=0..1000, before `*(420) D140 &6000 D150`. Product is 32-bit D150–151.
7. `/L(431) D150 D172 D160`: quotient D160–161, remainder D162–163. Low quotient 0..6000 is written once to each of CIO210/211.

**Do not** replace the `/L` divisor with immediate `&6000`/`&1000` without proving its 32-bit high-word representation. Here the divide source is always a memory pair populated by `MOVL`; there is no inherited high word. The two constants also form correct 32-bit offsets for subtraction. All four result words of each `/L` are allocated and do not overlap sources/divisors/other instructions.

| Area | Owner and length |
|---|---|
| CIO200–203 | AI0–3 read-only; D100–103 guarded copy |
| W0.00–.03 | AI0–3 valid; W0.04 output_valid; W0.05 scaled_valid |
| D104 | Signed-clamped raw AI0 0..6000 |
| D110–111 | 32-bit input product |
| D120–121 / D122–123 | Input quotient/remainder each 32-bit |
| D130–131 | HMI signed 32-bit scaled_input, unit 0.1 |
| D140 | output_command after signed clamp 0..1000 |
| D150–151 | 32-bit output product |
| D160–161 / D162–163 | Output quotient/remainder each 32-bit |
| D170–171 | Signed 32-bit divisor constant=6000 |
| D172–173 | Signed 32-bit divisor/offset constant=1000 |
| D200 | Signed 16-bit HMI command, unit 0.1% |
| CIO210/211 | One final writer per AO, both from D160 |

Product, quotient, remainder, and engineering defaults are cleared in pairs each scan before conditional math. Thus when AI0 is invalid the HMI engineering value becomes 0 and `scaled_valid` false, not an old value still appearing valid. If only AI1/3 fails, AI0 engineering may still be valid but `output_valid` is false and both AO are low; the HMI must distinguish the two flags.

## Numeric limits and rounding

With clamping before multiplication, maximum input product 6000×2000=**12,000,000** and maximum output product 1000×6000=**6,000,000**. Both are well above 65535/signed16 but below 2,147,483,647 signed32. Since divisors are fixed positive 6000/1000, there is no divide-by-zero or undefined −2³¹/−1 case. Span/range changes require proof of new bounds; a 32-bit destination does not justify arbitrary multipliers.

| Raw AI0 | Engineering tenths | Command tenths% | Raw AO |
|---:|---:|---:|---:|
| 0 | −1000 | 0 | 0 |
| 1500 | −500 | 250 | 1500 |
| 3000 | 0 | 500 | 3000 |
| 6000 | +1000 | 1000 | 6000 |

Integer division truncates toward zero. Since the input dividend is nonnegative, raw 1 gives quotient 0, remainder 2000, then −1000; raw 5999 gives quotient 1999, remainder 4000, then 999. This is intentional quantization, not floating point. Raw AI1/3=0 still means 4 mA; the input scaling example uses AI0 voltage, but never applies a 1200 offset to current channels.

## Edge cases in JSON

- First scan even if ready; endpoints 0/6000, midpoint 3000, and negative engineering −500/−1000 (high word #FFFF).
- Product 12,000,000=high 183/low 6912 and 6,000,000=high 91/low 36224: nonzero high words show that expectations require 32 bits, not a wrapped 16-bit result.
- Non-exact division raw 1/raw 5999 checks remainder in the second pair.
- Input −300/6300 is saturated; bit patterns −32767/32767 are also clamped before multiplication; sentinel #8000 is invalid, not valid scaled low.
- Command −1/#8000/1001/32767 is clamped before multiplication; no negative/over-6000 AO result.
- System error, readiness drop, open AI1/AI3, #8000, and recovery after previously nonzero values: clear value, validity flag, output low, and fresh recomputation.

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

- [W451-E1-03](https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1), §3-7-3 p.250 (PDF283): MOVL(498) two words; §3-10-10 pp.353–354 (PDF386–387): -L(411); §3-10-17 pp.369–371 (PDF402–404): *(420) 16×16→32; §3-10-24 pp.380–381 (PDF413–414): /L(431) 32-bit dividend/divisor, four-word quotient+remainder result; §3-17-7/8/9 pp.653–663: SCL/SCL2/SCL3 types are not directly signed 32-bit binary.
- [W474-E1-13](https://files.omron.eu/downloads/latest/manual/en/w474_cs_cj_nsj-series_plc,_sysmac_one_nsj_series_reference_manual_en.pdf?v=1), pp.286–287 (PDF320–321) and pp.292–293 (PDF326–327): cross-check multiply/divide operands and divisor-zero ER. W451 establishes CP1H support; the W474 CPU list is not the basis for CP1H support. W451 p381 has incorrect flag prose; use W474's clarification rather than treating a zero result as an error.

The results table and bounds are design arithmetic derivations, not PLC/simulator readings. All text and ladder are original and do not include vendor manuals.
