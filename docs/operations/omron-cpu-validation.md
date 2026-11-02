# Omron CPU validation: 2026-11-02

## Scope and ownership

This is a local correction to the installed, external `CX-Programmer-MCP` backend,
plus a small fix to this repository's original MCP example client. It is not a new
in-repository Omron backend. The external implementation has no published license;
its source and local modifications are not bundled or published here.

The public client fix is in `contoh/omron/mcp_build.py`: the tool selector argument
is named `tool_name`, so `omron_set_symbol` can receive its required `name` payload
without a Python argument collision.

## Reproduced failures and corrections

- The external project parser returned `CP1E` for every device except CP1H. In
  particular, its device pattern did not preserve the hyphen in `CP2E-N`.
- Unknown device names silently used the CP1E memory map. The local correction
  requires one explicit saved device identity and rejects unknown profiles.
- The CP2E-N validator rejected valid upper addresses such as `W127.15`,
  `H127.15`, and `D16383`. It now has an explicit CP2E-N map.
- The instruction helper incorrectly prohibited binary timers/counters outside
  CP1H. It now checks `TIMX(550)` and `CNTX(546)` operands rather than prohibiting
  instructions documented for CP1E/CP2E.
- Timer/counter numbers are checked against their own areas, not mistaken for CIO
  word operands. Presets are checked for unsigned 16-bit range and, for `TIM`/`CNT`,
  packed BCD. Literal operand address bounds are checked, including operands
  without a symbol declaration.

The legacy standalone address API still explicitly selects CP1E when passed
`None`; a missing saved project device does not use that default. Symbolic type
resolution, indirect operands, multiword spans, full instruction availability,
read-only system-area restrictions, and timer/counter mode settings still require
the vendor compiler. An address range is not a physical I/O allocation or a grant
to write system memory.

## Evidence obtained

The CPU regression tests were observed failing before correction and passing
afterward. The local test command is:

```bash
python3 -m unittest discover -s tests -p test_cpu_validation.py -v
```

Run that command from the separately installed external backend checkout. It is
not part of this public checkout and is not installed by this repository.

Initial CP1H/CP2E verification, before the CP1L/CJ2M expansion:

- External CPU regression suite: **15 tests passed**.
- Public repository suite: **220 passed, 3 skipped, 24 subtests passed**
  (`python3 -m pytest tests backends -q -p no:cacheprovider`).
- Canonical checks: **7 examples, 8 programs, 40 offline scenarios passed**;
  the native counts in that check are recorded evidence, not a new compiler run.
- HMI-AI/Content Studio synchronization: **2 consumer indices and read-only HMI
  bindings passed**, with canonical manifests and bindings intentionally unchanged.
- `python3 scripts/check_large_files.py --max-mb 2` exited successfully.

Actual Windows MCP subprocesses were exercised through the multi-plc-agent stdio
router using new synthetic projects, with editor auto-reload disabled:

| Target | Authored rungs | MCP write/save | Read-back in a new backend process | Invalid symbol | Invalid timer commit |
| --- | --- | --- | --- | --- | --- |
| CP1H-X40DT-D, device CP1H / CPU X | 10 | Passed | Identical instructions and boundary symbols | Rejected | Rejected; saved CXT unchanged |
| CP1H-XA40DT-D, device CP1H / CPU XA | 10 | Passed | Identical instructions and boundary symbols | Rejected | Rejected; saved CXT unchanged |
| CP2E-N30DT-D, device CP2E-N / CPU N | 10 | Passed | Identical instructions and boundary symbols | Rejected | Rejected; saved CXT unchanged |

Each synthetic program contains `TIMX`, `CNTX`, completion contacts, `DIFU`, `DIFD`,
`KEEP`, `OUTNOT`, and internal-memory boundary accesses. No physical output or
online tool was used. The probe establishes file editing, validation, persistence,
and read-back, not instruction execution or timer accuracy.

The initial machine-local inputs, CXT/CXP pairs and RPC receipts remain under
`_scratch/omron-cpu-validation-20261102/`. The corrected sources are now published
with the [seven CPU probes](../../contoh/omron/cpu-probes/), separately from the
canonical teaching-case manifests and HMI bindings. Restart an already-running
Omron backend to load local source corrections; a mounted server may retain its
old module.

## Native compile status and publication scope

All seven new instruction probes now have observed native compile and
save/reopen/recompile success in CX-Programmer 9.75, with matching saved-CXP MCP
read-back. CX-Simulator and physical PLC execution remain `not_run`. The older
canonical examples retain their own receipts; they are not reused as proof for
the new probes.

Policy correction: the repository does **not** require simulation or physical PLC
testing before committing original code, publishing examples, or recording a GIF.
`CONTRIBUTING.md` requires real vendor compile/build evidence and matching
read-back when claiming a newly verified backend/target. `RELEASING.md` defines
the release checks; neither document makes physical commissioning a release gate.
The existing Omron examples use matching MCP read-back of the saved project plus
the real compiler's diagnostics. A separate vendor-export round trip can improve
evidence where available, but is not a new universal requirement in
`CONTRIBUTING.md`.

The native run used owned fresh CX-Programmer processes and synthetic project
copies in the authorized primary Windows session. Actual UIA access, unlocked
Default desktop, version 9.7.5.6 and equal Medium integrity (RID 8192) were checked.
Native controls were inspected and scoped to the exact process/window. Only owned
processes were saved and closed; no account, VM, elevation, installation or live
PLC operation was used. This is not full profile/system isolation: normal native
application recent-file/view state may persist.

Before agent-driven desktop interaction, evaluate the selected runner's
authorized session, owned process/project, scoped controls and applicable fixture
requirements. Do not silently take over an unrelated project, elevate privileges
or provision accounts, VMs or software. A runner precondition must be reported as
such; it must not prohibit independent offline work or accurately scoped
publication. The existing single-account decision is unchanged.

Original inputs, client changes, original native-saved projects, documentation and
privacy-reviewed GIF derivatives are publishable after the repository's checks.
The seven GIFs show two actual native step captures per CPU, not a continuous
screen recording or simulator trace. Simulation and hardware tests are separate
validation levels, required only for claims about those levels or commissioning.
The external backend's source/corrections remain local because a published
redistribution license has not been established.

## CP1L and CJ2M: completed offline stages

The execution order was revised with the maintainer's approval: finish the
independent offline stages in order (CP1H/CP2E, CP1L, CJ2M), then perform vendor
compile/read-back for new verified-target claims. Simulation and physical tests
are separate future validation work, not prerequisites for publishing these inputs.

The locally corrected backend now resolves both saved `DEV` and `CPU`, rather
than selecting a family-sized approximation. Area definitions contain explicit
intervals:

- CP1L M permits `D0`–`D32767`.
- CP1L L and L10 permit `D0`–`D9999` and `D32000`–`D32767`, not the gap between.
- CJ2M CPU31 permits `A0`–`A1471` and `A10000`–`A11535`, not the gap between.
- Missing/unknown CPU variants are rejected. Other CJ2 models and EM instruction
  operands remain unimplemented and are rejected rather than treated as symbols.

The original public loader has separate construction settings for CP1L M/L/L10
and CJ2M CPU31, based on installed numeric metadata facts. It does not reuse
CP1H program-memory capacity or L10 capability flags blindly.

The earlier four CP1L/CJ2M inputs were built through actual MCP subprocesses,
with 11 rungs each. Saved instructions and boundary symbols matched after backend
restart. Invalid symbols, timer numbers, CP1L DM-hole accesses, CJ2 Auxiliary-hole
accesses and EM operands were rejected; failed commits left saved CXT unchanged.
The three 10-rung CP1H/CP2E probes also passed that offline regression. Those
earlier receipts were MCP-only; the native results below are a subsequent run.

The expanded external regression suite passed **24 tests**, observed failing
before the variant implementation. Historical raw receipts remain local under
`_scratch/omron-cpu-variants-20261102/acceptance/`. The current public evidence pins
the corrected source and native artifacts rather than retaining stale source
hashes from the earlier MCP-only attempt.

Earlier offline-only verification also passed the public repository suite (**220
passed, 3 skipped, 24 subtests passed**), the **40** canonical offline scenarios,
both sibling consumer indices, read-only HMI bindings, and the file-size/media
guard. No canonical manifest or HMI address/binding was changed for these probes.

HMI-AI and Content Studio continue to pin the existing seven canonical examples.
Do not add unpublished probes, fake manifests, empty bindings, or replacement
hashes to make synchronization checks pass.

## Native completion: actual failure, correction and verification

The first CP1H compile failed with four errors: `TIMX(550)` and `CNTX(546)` were
invalid function names while the project's Binary timer/counter option was off.
The native PLC Properties checkbox confirmed that state. Enabling it changed the
errors to incorrectly positioned functions. The controlled MCP-authored seed
using plain `TIMX` and `CNTX` plus the native resource field
`TCSettingBinary:=1;` then compiled with **0 errors / 0 warnings**.
The public loader now selects the mode from `timer_counter_mode` and rejects a
mismatched template before output/backend writes. Its regression test failed
before that correction and passed afterward.

The same flow then completed in order for all seven representative targets:

| Native family / CPU | Authored rungs | Initial compile | Save/reopen/recompile | Fresh saved-CXP MCP read-back |
| --- | --- | --- | --- | --- |
| CP1H / X | 10 | 0 errors / 0 warnings | Passed | Matched |
| CP1H / XA | 10 | 0 / 0 | Passed | Matched |
| CP2E-N / N | 10 | 0 / 0 | Passed | Matched |
| CP1L / M | 11 | 0 / 0 | Passed | Matched |
| CP1L / L | 11 | 0 / 0 | Passed | Matched |
| CP1L / L10 | 11 | 0 / 0 | Passed | Matched |
| CJ2M / CPU31 | 11 | 0 / 0 | Passed | Matched |

The native-saved CXP was copied byte-identically into a fresh read-only MCP
fixture with **no CXT sidecar**, preventing a stale text file from masking the
saved native result. Read-back explicitly accounts for verified function-number
annotations, `P_First_Cycle = A200.11`, decimal timer/counter zero-padding and
empty editor-only rungs. CP2E's three-digit formatting initially failed the strict
comparison; its actual values were inspected before adding that formatting rule.
Different addresses, presets, opcodes or function codes are not normalized away.

[Source-pinned evidence](../../contoh/omron/cpu-probes/mcp-evidence.json) includes
the native compiler input and final saved hashes, original CXP projects, decoded
CXT references, exact compiler output and seven GIFs. Decoded CXT is reference
text, not a separately tested vendor GUI export. Native view/save metadata can
change a file hash without changing its matched instructions. Full raw receipts,
failed experiments and window captures remain local under
`_scratch/omron-native-bmad-20261102/`; only reviewed synthetic derivatives are
published. GIFs are 960 pixels wide and below 2 MB, with no private desktop paths,
credentials, notifications or customer projects.

This verifies these instruction probes, not the entire CPU instruction set,
runtime timing, communication or physical safety. Other CP1L/CJ2 variants and EM
operands remain unverified. HMI/Content Studio still reference only the seven
canonical teaching cases; no fake manifests or writable bindings were added.

Final native-completion checks: the public suite passed **221 tests**, with
**3 skips** and **24 subtests**; the external CPU suite passed **24 tests**.
The canonical checker passed **7 examples / 8 programs / 40 scenarios**; both
consumer indices and the read-only HMI binding check passed. All seven published
source/project/CXT/GIF hashes and exact compiler logs matched their evidence.
Existing publication hooks, the production-dependency audit and media guard
passed. The router declares no runtime dependencies; this is not an audit of
every separately installed vendor/backend environment.


## Primary references

- [W614 CP2E Software User's Manual, E1-03, §5-1-3](https://assets.omron.eu/downloads/latest/manual/en/w614_cp2e_software_users_manual_en.pdf): CP2E memory ranges.
- [W483 CP1E/CP2E Instructions Reference, E1-08, pp. 2-72 and 2-86](https://assets.omron.eu/downloads/latest/manual/en/w483_cp1e_cp2e_cpu_unit_instructions_reference_manual_en.pdf): TIM/TIMX and CNT/CNTX.
- [W462 CP1L CPU Unit Operation Manual, E1-08, §4-10](https://files.omron.eu/downloads/latest/manual/en/w462_cp1l_cpu_unit_operation_manual_en.pdf?v=1): CP1L variant-specific DM ranges.
- [W473 CJ2 CPU Units Software User's Manual, E1-15](https://assets.omron.eu/downloads/latest/manual/en/w473_cj2_cpu_units_software_users_manual_en.pdf?v=6): CJ2 memory and configuration requirements.
- [W446 CX-Programmer Operation Manual, E1-23](https://files.omron.eu/downloads/latest/manual/en/w446_cx-programmer_operation_manual_en.pdf?v=1): vendor project and compiler workflow.

Manuals and installed vendor metadata are referenced, not redistributed.
