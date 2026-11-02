# Original prompt: signed 32-bit scaling on CP1H XA

Create an original English-language LD tutorial for Omron **CP1H-XA40DT-D**, device `CP1H`, CPU `XA`, in folder `04-analog-scaling`. Do not replace the CPU with CP1E. Do not copy manuals, vendor projects, or third-party tool source. Do not create stubs, fake native projects, a new interpreter, or a manifest. Do not download, go online, force, write live values, access hardware/COM/USB/serial, install software, or modify hardware.

## Files and evidence limits

Generate `program.json` with `schema_version:1`, `id:"04-analog-scaling"`, model/device/cpu as above, `sections:[{name,rungs:[{comment,instructions:[string]}]}]`, and `scenarios:[{name,scans:[{dt_ms,inputs,expect}]}]`. Instructions are CX-Programmer mnemonics forming LD rungs. Create `signals.csv` with exactly the columns `signal,address,type,unit,hmi_access,description`, an English `README.md`, and `prompt.id.md` containing this complete reproduction prompt.

Run `python3 contoh/omron/check.py` for the offline mnemonic model, then use the MCP router to write and read back LD. Compile in CX-Programmer with the CP1H XA profile; save actual compiler output separately from offline model results. If File/New CX-Server fails, the original XA text seed from `mcp_build.py --draft-seed` may be tried, but call it native-compiled only after the editor actually accepts it. Do not use a CP1E fixture as CP1H evidence. Do not claim CX-Simulator or hardware passed without separate authorized testing.

## Fixed device configuration

All four AI and two AO `Use`; common resolution **6000**. AI0/AI2 0–10 V mode with physical switch OFF; AI1/AI3 4–20 mA mode with switch ON. All AI averaging OFF. AO0 0–10 V mode and AO1 4–20 mA mode. Configure only through **CX-Programmer PLC Setup → Built-in AD/DA**, with the vendor transfer and power-cycle procedure. Do not write A75–A78, A600-series, A642/A643, or expansion initializer CIO102 as XA setup.

CIO200–203 are AI0–3; CIO210/211 are AO0/1. Also document 24 digital inputs CIO0.00–0.11 and 1.00–1.11 and 16 sinking outputs CIO100.00–100.07 and 101.00–101.07; this analog ladder does not use digital terminals. Do not assume contiguous ranges.

## Readiness, validity, and HMI

For each channel, calculate validity W0.00–.03 from A434.04 ON=initialization completed, NOT A315.14 error, NOT A200.11 first cycle, and raw not #8000. AI1 and AI3 also require NOT A434.01/.03 open-circuit. Do not treat #8000 as measurement −32768. Clear D100–103 to 0 each scan then populate only with valid channel raw values. Invalid data must not appear stale as valid.

W0.04 `output_valid` requires all four AI valid. W0.05 `scaled_valid` follows only AI0 validity; if AI1/3 faults, AI0 engineering may remain valid but both AO must be low. This is conservative application policy, not mandatory vendor behavior.

Required signal IDs: `analog_input_0..3` at D100–103, `analog_valid_0..3` at W0.00–.03, `analog_output_0/1` at CIO210/211, `scaled_input` of type DINT at D130, `scaled_valid`, `output_valid`, `output_command` of type INT at D200, and `output_command_clamped` at D140. Application command may be read_write; raw, status, and actual output read only. The HMI must use the value with its validity bit, not treat 0 as automatically valid.

## Signed 32-bit input scaling path

Compare the SCL family options involving BCD with signed 32-bit binary arithmetic. Choose `*(420)` signed16×signed16 producing 32 bits, `/L(431)` with 32-bit dividend and divisor, and `-L(411)` 32-bit offset. Do not use ordinary `/(430)` on the product low word. Do not assume `/L` reads the entire 64-bit `*L` result. Do not use `MOVL 200 D100` for sign extension, because the AI1 word would become the high word.

1. **Signed** clamp D100 to D104=0..6000 before multiply; default D104=0 each scan. Extended input −300 becomes 0 and 6300 becomes 6000. Valid #8000 must already have been rejected before this stage.
2. `*(420) D104 &2000 D110` writes signed 32-bit product D110–111.
3. `MOVL(498) &6000 D170` sets the pair D170 low=6000/D171 high=0 every scan with P_On.
4. `/L(431) D110 D170 D120` writes quotient D120–121 and **remainder D122–123**; all four words must be allocated.
5. `MOVL(498) &1000 D172` sets D172 low=1000/D173 high=0 every scan, also the output divisor and input offset constant.
6. `-L(411) D120 D172 D130` produces signed 32-bit engineering D130–131 according to `(raw×2000)/6000−1000` in 0.1-unit increments, range −1000..+1000.

Do not give immediate `&6000` or `&1000` directly to `/L` without proving its 32-bit high-word representation. This example deliberately uses memory pairs established by MOVL. The subtraction offset must also come from an explicit pair. Use signed comparators `AND<S(312)`, `AND>S(322)`, `AND>=S(327)`, and `AND<=S(317)`; comparators without suffix S are unsigned.

## Output scaling path and one final writer

Signed 16-bit command D200 in 0.1% has application range 0..1000. Gate on all AI valid, then clamp signed to D140=0..1000 **before** multiply. D140 defaults to 0 each scan; negatives remain 0 and values above 1000 become 1000.

`*(420) D140 &6000 D150` writes signed 32-bit product D150–151. `/L(431) D150 D172 D160` writes quotient D160–161 and remainder D162–163. Only one `MOV(021) D160 210` and one `MOV(021) D160 211` at the end of the program write the physical AO.

Before conditional mathematics, clear pairs D110, D120, D122, D130, D150, D160, D162 using MOVL 0 each scan. On startup or fault, quotient and engineering must not use stale values; both AO raw 0. Reserve all pairs without overlap. Maximum input product 12,000,000 and maximum output product 6,000,000: both exceed 16 bits but fit signed 32 bits. Positive fixed divisors prevent divide-by-zero and −2³¹/−1. Span changes require a new bound calculation.

Document integer truncation: raw 0→−1000, 1500→−500, 3000→0, 6000→1000; raw 1 has quotient 0/remainder 2000, raw 5999 quotient 1999/remainder 4000. Command 0→raw 0, 250→1500, 500→3000, 1000→6000. Raw 0 in 4–20 mA means 4 mA, **not 0 mA**; do not subtract 1200. Program raw 0 is not a guarantee of physical fault output or a safe process condition. The program does not change A500.12 hold. Emergency stop, guard, overload, and energy isolation require separate safety equipment/design.

## Acceptance scenarios

Include scans that will execute the original JSON mnemonics: first cycle even if ready, readiness incomplete, endpoints, midpoint, negative engineering with high #FFFF, maximum product with nonzero high word, non-exact division, extended input −300/6300, signed extremes −32767/+32767, sentinel #8000, command −1/#8000/1001/32767, error after nonzero data, readiness drop, AI1/AI3 open circuit, recovery, and evidence that stale data is not published as valid.

Each scenario starts with fresh state. The checker generates `A200.11` on the first scan. Inputs persist until changed. Negative memory values are written as unsigned 16-bit bit patterns: −300=65236, −1000 low 64536/high 65535, −500 low 65036/high 65535. Do not describe these arithmetic expectations as simulator results.

## Primary sources and pages

- W450-E1-08: https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1 — §4-2-2p153, §4-3p159, §5-5pp326–337, Appendix G pp761–762, §11-2p614, Appendix C p648.
- W451-E1-03: https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1 — §3-6-1pp211–214, §3-7-3p250, §3-10-10pp353–354, §3-10-17pp369–371, §3-10-24pp380–381, §3-17-7/8/9pp653–663.
- W474-E1-13: https://files.omron.eu/downloads/latest/manual/en/w474_cs_cj_nsj-series_plc,_sysmac_one_nsj_series_reference_manual_en.pdf?v=1 — pp286–287 and 292–293 for operand cross-check and divisor-zero ER clarification. W451 establishes CP1H support; W474's model list is not evidence for it. W451 p381 has a flag prose error; do not describe a zero result as an error.

Separate manual facts, original design, arithmetic derivation, offline expectations, and actual execution evidence. All text and ladder must be written independently and suitable for engineer review before use on a machine.
