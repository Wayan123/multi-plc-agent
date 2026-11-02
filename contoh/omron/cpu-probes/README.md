# Omron CPU instruction probes: native compile and saved-project read-back

Seven original LD programs were generated through the **multi-plc-agent stdio
router and Omron MCP**, then opened in **CX-Programmer 9.75 (9.7.5.6)**. Every
project compiled with **0 errors / 0 warnings**, was saved, closed, reopened and
compiled again. A fresh, read-only MCP process read the native-saved CXP and
matched the authored instructions and CPU profile.

**No CX-Simulator or physical PLC test was performed.** These are instruction and
memory-boundary probes, not new conveyor/traffic-light runtime demonstrations.
The seven canonical teaching cases and their HMI/Content Studio references remain
separate and unchanged.

| Source | Representative model label | Saved device / CPU | Rungs | Ready project | Native step GIF |
| --- | --- | --- | --- | --- | --- |
| [CP1H_X.json](CP1H_X.json) | CP1H-X40DT-D | CP1H / X | 10 | [CXP](projects/CP1H_X.cxp) | [GIF](../../../docs/demo/omron-cpu-CP1H_X.gif) |
| [CP1H_XA.json](CP1H_XA.json) | CP1H-XA40DT-D | CP1H / XA | 10 | [CXP](projects/CP1H_XA.cxp) | [GIF](../../../docs/demo/omron-cpu-CP1H_XA.gif) |
| [CP2E_N.json](CP2E_N.json) | CP2E-N30DT-D | CP2E-N / N | 10 | [CXP](projects/CP2E_N.cxp) | [GIF](../../../docs/demo/omron-cpu-CP2E_N.gif) |
| [CP1L_M.json](CP1L_M.json) | CP1L-M40DT-D | CP1L / M | 11 | [CXP](projects/CP1L_M.cxp) | [GIF](../../../docs/demo/omron-cpu-CP1L_M.gif) |
| [CP1L_L.json](CP1L_L.json) | CP1L-L20DT-D | CP1L / L | 11 | [CXP](projects/CP1L_L.cxp) | [GIF](../../../docs/demo/omron-cpu-CP1L_L.gif) |
| [CP1L_L10.json](CP1L_L10.json) | CP1L-L10DT-D | CP1L / L10 | 11 | [CXP](projects/CP1L_L10.cxp) | [GIF](../../../docs/demo/omron-cpu-CP1L_L10.gif) |
| [CJ2M_CPU31.json](CJ2M_CPU31.json) | CJ2M-CPU31 | CJ2M / CPU31 | 11 | [CXP](projects/CJ2M_CPU31.cxp) | [GIF](../../../docs/demo/omron-cpu-CJ2M_CPU31.gif) |

The product labels do not identify connected hardware or prove electrical I/O
configuration. The compiler checked the saved family/CPU. Other CP1L/CJ2 models,
indirect addressing, EM operands and the full vendor instruction sets are not
covered. The corrected local validator rejects unsupported variants and EM
operands rather than guessing a memory map.

## Open a ready project

1. Use your licensed CX-Programmer installation and open a linked `.cxp` above.
2. Keep the project **Offline**. No connection, download or I/O forcing is needed.
3. Open `ExamplePLC → Programs → Main (00) → Instruction_Probe`.
4. Select the PLC and run **PLC → Compile All PLC Programs**. Compare the full
   output with the matching file in [evidence/](evidence/).
5. Inspect the CPU profile and **Execute Timer/Counter as Binary** in PLC
   Properties before adapting the example. Do not download these boundary probes
   to a controller: they intentionally use upper internal-memory addresses.

The accompanying `.cxt` files are decoded reference text from our native-saved
CXP files, **not a separately exercised GUI-export/import round trip**. Use the
CXP files for the verified opening path.

## What the ladders contain

All outputs are internal memory, not physical terminals:

1. Binary 100 ms `TIMX` with decimal preset 10: one second by specification.
2. Binary `CNTX` with count/reset inputs and first-cycle initialization.
3. Timer completion copied to an internal bit.
4. Counter completion copied to an internal bit.
5. `DIFU(013)` rising-edge output.
6. `DIFD(014)` falling-edge output.
7. `KEEP(011)` latch with first-cycle reset.
8. `OUTNOT` inverted output.
9. Work/holding upper-bound bit access.
10. A constant written to the upper DM word.
11. For CP1L, an allowed DM-segment read; for CJ2M, an extended read-only Auxiliary
    read. This last rung is not included in the three CP1H/CP2E probes.

CP1L M has contiguous DM through D32767. L/L10 have D0–D9999 and
D32000–D32767, so D20000 must be rejected. CJ2M CPU31 has Auxiliary ranges
A0–A1471 and A10000–A11535, not A9999. These interval rules are documented and
covered by local backend regression tests; the native probes are not an
exhaustive sweep of every address or instruction.

Timer duration, edge pulses and reset priority have **not** been measured on a
vendor runtime. The limited `offline.py` teaching evaluator does not implement
this complete instruction set; no empty scenario list is used to invent a
passing simulation result.

## Rebuild through MCP

Use a Windows Python interpreter able to launch your configured router and
external Omron server. The local backend needs the explicit CPU/interval
corrections described in [the validation record](../../../docs/operations/omron-cpu-validation.md).
Its implementation has no published redistribution license and is **not bundled
here**; the results do not imply that an unmodified upstream backend supports
these profiles. Opening the supplied CXP files does not require that backend.

From the repository root, replace these example paths with your own:

```powershell
python contoh/omron/mcp_build.py `
  --config C:\local\multi-plc-config.json `
  --program contoh/omron/cpu-probes/CP1L_M.json `
  --output C:\local\new-cp1l-probe\instruction_probe.cxt `
  --draft-seed `
  --receipt C:\local\new-cp1l-probe\mcp-receipt.json
```

Choose a new output directory for each CPU. The loader refuses existing outputs,
keeps editor auto-reload disabled, writes through MCP and compares instructions
and CPU. The JSON explicitly selects `"timer_counter_mode": "binary"`; the
original seed records the native resource setting `TCSettingBinary:=1;`. A
provided template with a different timer/counter mode is rejected before writing.
Programs without the field retain BCD mode.

Two native failures exposed the required authoring details: an absent Binary
setting made the binary timer/counter names invalid; after enabling it, the
initial seed still rejected the decorated spellings as incorrectly positioned.
Use `TIMX` / `CNTX` in the authored seed input. CX-Programmer itself displays and
saves their function-number annotations, `TIMX(550)` / `CNTX(546)`, after parsing.
Do not remove annotations indiscriminately from vendor-saved projects.

The loader's MCP result is **not** a native compiler result. Repeat the native
open/compile/save/reopen/compile and saved-file read-back when changing source.

## Evidence, GIFs and publication

[mcp-evidence.json](mcp-evidence.json) pins the seven source files, original native
projects, compiler inputs/final saves, decoded references and GIFs by SHA-256.
[evidence/](evidence/) contains the actual compiler output. The native-saved CXP
was read by a fresh **read-only** MCP with no stale CXT sidecar. Read-back compares
instruction semantics, allowing only verified function-code annotations,
`P_First_Cycle = A200.11`, decimal timer/counter zero-padding and empty editor-only
rungs. Different addresses, presets, instruction names or function codes are not
silently accepted.

Each GIF contains **two actual window-only step captures**, before save and after
reopen/recompile. They are cropped/resized and privacy-reviewed, not continuous
screen recordings, simulator traces or evidence of physical operation. All are
960 pixels wide and below the repository's 2 MB limit. Raw desktop receipts and
images remain local; no MP4 is added to GitHub.

The run used the authorized primary Windows account, owned fresh processes,
synthetic projects, equal Medium integrity and verified UIA controls. It is not
full profile/system isolation; normal application recent-file/view state may
persist. Only owned processes were closed. No account, VM, installation, online
connection, download, force operation or runtime activation was used.

Native compile plus matching saved-program MCP read-back follows the existing
Omron acceptance pattern. Simulator/physical tests are separate evidence levels,
not new prerequisites for a GIF, commit or publication. HMI-AI and Content Studio
retain their seven canonical references and no writable binding is introduced.

Sources: [W462 CP1L, §4-9-3 and §4-10](https://files.omron.eu/downloads/latest/manual/en/w462_cp1l_cpu_unit_operation_manual_en.pdf?v=1),
[W473 CJ2, §6-1](https://assets.omron.eu/downloads/latest/manual/en/w473_cj2_cpu_units_software_users_manual_en.pdf?v=6),
and numeric CPU/default-allocation facts observed in installed CX-Server metadata.
Vendor metadata files and third-party backend source are not redistributed.
