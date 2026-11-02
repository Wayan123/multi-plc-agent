# CP1H-X40DT-D: four-approach traffic light and pedestrian crossing

**Offline educational example**, not a ready-to-use intersection controller or a certified safety function, and it must not be installed on public roads. Public roads require an independent safety controller, an approved intersection design, hazard analysis and validation by the relevant authorities. This program does not detect lamp failures, stuck outputs, short circuits, physical conflicts, loss of power or CPU failures; it does not guarantee all red when the PLC stops or loses power. PLC outputs are commands, not proof that lamps are lit. No flashing state is claimed to be safe.

## Scope and assumptions

CPU **CP1H X** (CP1H-X40DT-D), sinking transistor outputs. Each approach has three separate output addresses. The phase sequence still pairs north–south and east–west; there are not four separate green phases. The north-side pedestrian crossing operates automatically during a dedicated all-vehicles-red phase, without a request button. When pedestrians are green, all vehicle movements, including turns, are prohibited. Turn arrows, emergency vehicles, detectors, a separate pedestrian clearance time, equipment interlocks and lamp monitoring are not modeled. Turning conflicts between vehicles have not been analyzed.

Each lamp uses one output; check transistor ratings, inrush current, common and supply in the manual. If necessary use a suitably designed interface driver; this example does not authorize wiring or physical use.

| CIO output | Function |
|---|---|
| 100.00 / .01 / .02 | north red / yellow / green |
| 100.03 / .04 / .05 | south red / yellow / green |
| 100.06 / .07 / 101.00 | east red / yellow / green |
| 101.01 / .02 / .03 | west red / yellow / green |
| 101.04 / .05 | pedestrian red / green |

All outputs use one `OUT` per address. There are no physical inputs, buttons or HMI writes; `D0` is written only by the program. Built-in physical output terminals are CIO 100.00–100.07 and 101.00–101.07, not 100.00–100.15. Built-in inputs are CIO 0.00–0.11 and 1.00–1.11. Addresses not listed in `signals.csv` are not used by the program. Do not assume spare outputs are controlled or safe.

## Illustrative sequence and timing

`D0` is the stage number in BCD format; `TIM 0000`–`0008` use BCD presets in units of 0.1 s. Each stage is evaluated in order: first-scan initialization, all timers, stage transitions, then outputs. The new phase appears at the outputs on the transition scan; its timer starts being evaluated on the next scan. `A200.11` on the first scan forces D0=0 even if previous memory was retained. Phase 0 is startup only; after phase 8 the cycle returns to phase 1.

| D0 | Nominal duration | North/south | East/west | Pedestrian |
|---:|---:|---|---|---|
| 0 | 2 s | red | red | red |
| 1 | 10 s | green | red | red |
| 2 | 3 s | yellow | red | red |
| 3 | 2 s | red | red | red |
| 4 | 10 s | red | green | red |
| 5 | 3 s | red | yellow | red |
| 6 | 2 s | red | red | red |
| 7 | 5 s | red | red | green |
| 8 | 2 s | red | red | red |

The repeating cycle is nominally 37 s after the 2 s startup, plus scan effects and timer tolerances. These durations are illustrative only, **not** traffic-engineered values or adequate crossing times. All-red transitions occur before each group change and before/after the pedestrian phase. No vehicle movement phase occurs while pedestrians are green. If D0 is outside 0–8, the output equations command all red and do not correct the stage; this is not an independent safety mechanism and does not cover output or memory failures.

## Files and usage

- `program.json`: rung mnemonics and scenarios; one instruction array is one rung.
- `program.il`: mnemonic listing derived from the JSON sections/rungs, not native compilation output.
- `signals.csv`: addresses used and timer status; `read` means observation, not permission to write.
- `prompt.id.md`: requirements for reproducing the example.

From the repository root, run `python3 contoh/omron/check.py` and `python3 -m unittest discover -s tests -p test_traffic_light.py -v`. This is a limited offline mnemonic model, **not** CX-Simulator or a physical test. Tests check 14 outputs, including all vehicles red while pedestrians are green; D0 injection is only in the evaluator.

The `mcp/` project and compiler results must be rebuilt after program changes; see evidence tied to the current source hash in `mcp/*.verification.json`. Do not download, go online, force, or connect hardware based on this example.

## Primary sources

- [Omron W450 CP1H CPU Unit Operation Manual](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §1-2 and §4-2-2: model, I/O ranges; Appendix C: `A200.11` first cycle. Check the model's electrical specifications and common before selecting a load.
- [Omron W451 CP1 CPU Unit Programming Manual](https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1), §3-5-1: `TIM`, BCD 0.1 s and reset; §3-6/3-7: comparisons and `MOV`. The phase sequence and timing values are example choices, not a certified example from Omron.
