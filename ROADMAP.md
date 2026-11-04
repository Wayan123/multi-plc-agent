# Roadmap

A status is recorded only after it has been run on real software. "Planned" means the named target/scope has not yet met native acceptance, even when a backend already supports a different target.

## GX Works3 (Mitsubishi iQ-F / iQ-R): blocked on the development machine

GX Works3 **1.055H** is installed on the development machine, but [Project] > [New] fails every time (6 of 6 tries, FX5U and R00): "Unable to execute the operation because memory is insufficient or system is unstable", then "R6025 – pure virtual function call". Install logs show an aborted GX Works3/GX Works2 uninstall shortly before the first crash; the faulting component is not confirmed. A repair or reinstall is needed before the write path below can be run. The existing `.gx3` files are FX3U compatible-mode projects and can't serve as an FX5U template. Window-message command IDs that open New (`0x9000`) and Open (`0x9001`) without the foreground are known. The research below comes from the GX Works3 Operating Manual SH-081215ENG-AQ and from read-only checks of the installed resource DLLs. The full notes are in [docs/gxworks3-research.md](docs/gxworks3-research.md).

| Path | Works on 1.055? | Evidence | Plan |
| --- | --- | --- | --- |
| Ladder editor **[Edit] → [Import File]** (listed-instruction CSV) + device comment CSV import | Yes. Added in 1.030G; labels/inline ST/FB in 1.040S, undefined FB/FUN in 1.055H | Manual §6.3 p.386–395, §6.8 p.499–500. Strings in `LadderEditor_RC2.dll` and `CommentEditor_RC2.dll` | **Primary.** This replaces GX Works2 "Read from CSV File" (manual Appendix 14, p.1221). gxworks-agent already writes the same 7-column UTF-16 CSV |
| Open I/F COM server `GXW3Call.dll` (`CreateNewProject`, `ImportProjectXml`, `BuildProject`, `SaveProject`) | Registered locally, `GetOpenIFVersion` = 13 | Type library read with pywin32. Not documented publicly | Later. The calling protocol and licence are unknown, and the managed wrapper is not installed |
| **Open Other Format File** on a `.gxw` produced by gxworks-agent | FX3U/UC/G/GC → FX5U/UC only | Manual §3.2 p.118–121, handbook JY997D66201 §5.4 | Fallback / cross-check. Parameters reset, needs admin rights |
| Writing `.gx3` files directly | No | OLE compound file with Jet DB streams, undocumented | Not planned |

### First milestone

The milestone is complete when the agent writes an FX5U MAIN program (start/stop self-hold plus a timer, with device comments) and the backend does the following:

1. Imports the program into a new GX Works3 1.055 project through [Edit] → [Import File].
2. Imports the comment CSV.
3. Runs Convert with **0 errors**.
4. Exports the program back to CSV, with no differences from the file it imported.
5. Saves the project as `.gx3`.

GX Works3 will be listed as supported only once that run passes.

### Questions to answer hands-on first

1. What header and module-type lines does 1.055 write when exporting an FX5U program?
2. Does it accept a GX Works2-style CSV?
3. Can pywinauto/UIA reach the Codejock command bars, or are keyboard accelerators needed?
4. What changes are needed to lower ladder to FX5: SM/SD devices instead of M8000/D8000, and the FX5 forms of timers and counters?

## Installed engineering tools: digital I/O priorities

The development workstation has **TwinCAT XAE Shell 64-bit 9.0.2.0** and **DIADesigner 1.15.0.334**. On 2026-11-03 the user approved choosing the easiest installed-software-compatible target: TwinCAT RT x64 offline engineering now has a real verified MCP backend. CX7000/ARM and DIADesigner SV3 LD remain separate unchecked milestones. Installation alone is not support evidence.

| Priority | Digital target and evidence | Planned write path | First acceptance check |
| --- | --- | --- | --- |
| 1 | [Delta DVP28SV311S](https://landing.deltaww.com/en-US/products/PLC-Programmable-Logic-Controllers/DVP-SV3): SV3, 24 V DC, 16 DI / 12 PNP transistor DO, Ethernet; [Delta DVP catalog](https://deltaacdrives.com/Accessories/Delta-DVP-Series-PLC-Catalog.pdf), p.10 specifies DIADesigner | Build a separate DIADesigner MCP backend; preserve the existing WPLSoft ES2/SS2 backend. Investigate supported POU import/export or an official automation interface before considering scoped editor automation | Through the router, generate the shared conveyor from rung JSON, build in DIADesigner, save/reopen and compare vendor-produced read-back, including declarations and task assignment. A manually authored ladder is not backend acceptance |
| 2 | [Beckhoff CX7000](https://www.beckhoff.com/en-us/products/ipc/embedded-pcs/cx7000-arm-r-cortex-r/cx7000.html): physical/ARM target, still unverified | Extend the implemented public-Automation-Interface TwinCAT backend from its verified RT x64 target only after device/compiler/I/O configuration is established | Shared conveyor built for a verified CX7000 configuration and matching persisted task/LD readback; an x64 build alone is not CX7000 verification |

The CX7000's multifunction I/O also includes analog input capabilities; choosing it here does not imply the hardware is digital-only. Analog work, the DVP20SX311S, and the CX7000 + EL4374 + EL9011 configuration are outside these initial digital-only milestones.

### Verified TwinCAT RT x64 milestone — 2026-11-03

- Original backend [`backends/beckhoff`](backends/beckhoff/), router identity `twincat`, vendor/prefix `beckhoff` / `beckhoff_`.
- Actual `beckhoff_write_ladder`, independent `beckhoff_export_pou` and `beckhoff_build` ran through this router in three fresh owned XAE hosts; all hosts exited.
- Six-rung conveyor, eleven declarations, MAIN -> cyclic PlcTask / 10000 us, explicit TwinCAT RT (x64): native write and fresh rebuild each report **0 errors / 0 warnings / 0 failed projects**; exported logic, declarations and task binding match.
- Native import-in-memory alone was insufficient: a replacement could disappear after reopen. The writer uses a fresh owned project and public native POU cutover, then requires persisted readback. Explicit overwrite preserves the complete prior owned project in an unused sibling `.bak` directory.
- Three exact minimal standard-library packages were installed after sysinv preflight, reviewed feed dry-run and explicit owner authorization. No runtime activation, reboot, connection/download or physical I/O test occurred.
- [Original native example, request, receipts and reviewed native-step GIF](contoh/beckhoff/01-twincat-rt-x64-conveyor/). This does not claim CX7000, simulation, ADS/live values or functional safety.

Separate later result (2026-11-04): the [OIP conveyor pilot](contoh/beckhoff/02-oip-conveyor/) now runs its eight-rung native program on a dedicated **Usermode Runtime 1.27.1** after an operator-completed official TC1200 trial. The compiled/active boot app matches, and one full native ADS/Jolt wall-clock run passed **9 scenarios / 54 checks**. The initial timing miss is retained because usermode execution is not deterministic. This approved lab runner is separate from the offline MCP backend; no kernel configuration, additional driver or physical I/O was changed. CX7000/ARM remains unchecked.

**Current Delta result:** the agent created its own DVP28SV3 project, LD POU and Freewheeling (0) assignment and produced a genuine native `.export` with password protection disabled. That artifact is binary, not standard PLCopen XML/ZIP. A reliable supported LD placement/write/readback seam is still unproven; no DIADesigner backend or success GIF is advertised. Do not ask the operator to draw seed LD or decode/decrypt private vendor formats.

**User-approved Delta delivery:** use DVP-SS2 with installed WPLSoft 2.52 rather than block the current multi-vendor demonstration on the unverified SV3 seam. The existing `delta_` backend authored the [new original seven-rung example](contoh/delta/01-dvp-ss2-conveyor/), saved through WPLSoft, matched all saved instructions/device aliases and reopened/recompiled with 0 grammar errors. Native LD/IL step GIFs are included. No separate warning count, new family/backend, simulation or physical PLC claim is made. DIADesigner remains planned.



### Historical offline investigation — 2026-11-02

The following observations precede and are superseded by the measured 2026-11-03 outcomes above where they differ.

- **DIADesigner:** the operator's screenshots show `1.15.0`, a scratch project, `DVP-S III > DVP28SV3`, parameter version `01.08.30`, and an opened `MAIN_Digital` LD editor. Windows reports `1.15.0.334`. The installed **DIADesigner User Guide V1.15.0**, revision history, records SV3 support added in `1.3.0`; its compatibility table (printed p.723) explicitly marks DVP-28SV3 supported in V1.15. The older programming manual's `1.30` spelling is not grounds to declare 1.15 incompatible. The user guide documents POU `.export` import/export (pp.219–222), warns that imported POUs are not assigned to tasks, and documents compiled-program text export (p.423), not text import. No original `.export` seed or supported writable exchange has yet been established; the existing scratch `.diade` is not plain XML. Simulation documentation (p.511) lists AS100/AS200/AS300 only; SV3 simulation remains unverified. Exact ordering-code/output variant, native build and saved-program read-back remain unverified. Do not commit the vendor manual.
- **TwinCAT:** Windows reports XAE Shell 64-bit `9.0.2.0`, XAE Integration TcXaeShell64 `2.15.0.0`, and registered `TcXaeShell.DTE.17.0`. The operator's installed-package query confirms `TwinCAT.XAE.PLC.TcXaeShell64` `7.1.3` (component `4026.27.4.0`). The installed standard PLC template references `Tc2_Standard`, `Tc2_System`, and `Tc3_Module`; the package query `list TwinCAT.XAE.PLC.Lib --installed --as-json` returned `[]`, and no Tc2_Standard library was found in the inspected managed-library tree. Native library resolution still needs an actual project check, not an invented compiler error. Stable Feed offers `TwinCAT.XAE.PLC.Lib.Tc2_Standard` `3.4.7`. Beckhoff documents the [host ProgID](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/21842697995.html), [PLCopen exchange](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/21841320715.html), and [CX7000 ARMV7-M platform](https://github.com/Beckhoff/TwinCAT-Platform-Matrix). COM project creation, exact library resolution and CX7000 build are not verified; no extra package was installed during this probe.
- **Recorded execution evidence:** the initial session inspection exposed only the primary console account. Later operator screenshots establish manual Delta project/device/POU setup, not agent-executed GUI control. No new backend, native build, matched vendor read-back, simulation, physical PLC test or GIF is verified for either target. A separate Windows account does not isolate system-wide components, services or settings. Record actual outcomes and inspect recording frames for private data; simulation/hardware testing is not a prerequisite for publishing accurately labelled original work.
- **Delta read-only native access:** a live scratch-window probe on 2026-11-02 succeeded with equal Medium integrity (agent/editor RID 8192), no UI actions and exit 0. A targeted Project Explorer traversal completed without truncation; the observed tree contained the scratch project and Add Device but no controller/POU. Native project/device/save selectors exposed Invoke patterns; compile selectors were disabled. Full receipts and the bounded probe script are local under `_scratch/delta-sv3/`. This establishes read access only. Runner-specific write preconditions and any supported offline write API still need method-level verification. The inspected guide did not establish an application-profile switch; its command-line section concerns CARD Utility, not LD authoring. This is not a vendor requirement for a second account or proof that SV3 authoring is impossible.

### Windows account decision

Two Windows accounts are not a vendor prerequisite for these offline milestones. Keep the existing `wayandadang` WSL/agent environment; do not duplicate WSL or require account switching as the default workflow. The separate `wayan-plc` account is optional and does not isolate system-wide installations or services.

Project acceptance is defined by `CONTRIBUTING.md`, not by a mandatory second account, VM, simulator or physical PLC. An agent-driven desktop method must satisfy its own authorized-session, scoped-control and fixture/safety preflight; a scratch path alone does not establish profile isolation. Report a missing runner prerequisite as a limitation of that method, not an observed compiler failure, CPU incompatibility, or prohibition on accurately scoped commits/publication. Operator setup must not replace the missing backend or manual rung entry become the delivery path. Offline work excludes PLC connections, downloads, TwinCAT configuration activation and runtime mode changes.

### Backend delivery contract: DIADesigner and TwinCAT

The deliverable is two engineering backends exposed through the existing router, not a manual ladder tutorial, an HMI dashboard or two new LLM runtimes. Follow `CONTRIBUTING.md` and the existing stdio/rung contracts.

| Seam | DIADesigner SV3 | TwinCAT RT x64 verified; CX7000 still planned |
| --- | --- | --- |
| Proposed implementation location | `backends/diadesigner/diadesigner_mcp/` | `backends/beckhoff/beckhoff_mcp/` |
| Router identity | Proposed backend `diadesigner`, vendor `delta`, explicit prefix `delta_dia_` to avoid the existing `delta_` WPLSoft tools | Implemented backend `twincat`, vendor `beckhoff`, prefix `beckhoff_` |
| Surfaces | Read-only discovery and validate; gated project creation/write; native compile and vendor readback, once a real write seam is established | Implemented `list_targets`, `validate`, `write_ladder`, `build`, `export_pou`; no live-controller or general COM/shell executor |
| Remaining target prerequisite | Supported LD write/readback for the DVP28SV3 engine, declarations and persisted task binding | CX7000/ARM device/compiler/I/O identity; RT x64 libraries and native acceptance are resolved |

DIADesigner names remain proposals, not implemented tools. The TwinCAT backend is implemented only for the verified RT x64 scope. Keep WPLSoft callers unchanged; register no fake success tools or empty adapters.

Implementation sequence:

1. Inspect vendor-supported interfaces and the synthetic seed project without driving a personal project or bypassing licensing. Record exact software, device/profile and language support. Do not assume DIADesigner SV3 shares the CODESYS runtime or WPLSoft format.
2. Build the smallest complete backend path: rung JSON validation, generate one LD program, native project write/import, task/declaration verification, vendor build, save/reopen and independent read-back comparison. A generated XML file or self-comparison of input is insufficient.
3. Preserve `--allow-write`, explicit overwrite with backup, actionable failures and no live-controller operations. Run desktop backends serially on a shared desktop. Test consumer-visible invalid addresses/types, unsupported targets, write denial and read-back mismatches; exercise the actual stdio entrypoint and router.
4. Run the repository's shared conveyor through MCP: start/stop seal-in, simulated E-stop status/permissive, three-second warning horn, product counter with reset, stop at ten and batch lamp. Record tool calls, native build diagnostics and matching saved logic. A one-rung scratch test is an interface probe, not full backend acceptance.
5. Publish original examples, reproducible prompts, signal metadata and verification receipts under `contoh/`. Check README support boxes only after the real backend run meets `CONTRIBUTING.md`. Keep generated, built, read-back, simulated and physical-tested outcomes separate; record GIFs only from the actual completed workflow.

The earlier [DIADesigner SV3](docs/superpowers/plans/2026-11-02-diadesigner-sv3.md) and [TwinCAT CX7000](docs/superpowers/plans/2026-11-02-twincat-cx7000.md) plans remain historical design context. The user-approved RT x64 target correction and measured outcomes above supersede the original CX7000-first ordering; they do not turn x64 acceptance into ARM/hardware proof.


### HMI-AI integration boundary

`HMI-AI` is a separate sibling project, not a required PLC compiler or a substitute for a backend. Its current MCP surfaces are `hmi_list_backends`, `hmi_read_project` and `hmi_check_layout`; no native project writer or live PLC transport is implemented. Delta PLC support does not imply Delta DOPSoft support, and CX7000 support does not imply a TwinCAT HMI backend.

Reuse the ownership pattern already exercised by the Omron integration: PLC programs, models, addresses, types, units, access permissions and verification evidence stay canonical in multi-plc-agent. HMI stores logical signal references and reviewed source pins, not copied ladder/state machines or independently maintained addresses. Preserve command/status polarity, time units and validity semantics. New bindings remain read-only; do not grant PLC write permissions as a side effect of adding a backend.

The existing `HMI-AI/examples/conveyor/signals.csv` describes the earlier demos; its `delta_wplsoft` column is not an SV3 mapping. Add no SV3/CX7000 addresses until backed by the generated project/read-back. The Omron `check_sync.py` has fixed Omron model/example contracts; it is a reference pattern, not a generic checker for new vendors. Extend integration deliberately once real new manifests exist, without fake hashes, empty example entries, automatic cloning or publishing the local HMI repository.

Analysis smoke evidence (2026-11-02): an actual WPLSoft backend subprocess was discovered and called through `Router`; `delta_validate` returned expected IL without opening vendor software. The actual HMI stdio server exposed only its three read/check tools. The existing cross-project checker passed for seven Omron examples, two consumer indices (HMI-AI and Content Studio), and HMI bindings. These observations establish existing contracts, not SV3/CX7000 build or simulation support.



| Other target | Planned write path | First check |
| --- | --- | --- |
| Delta ISPSoft 3.x (DVP-SE/SV2, AS) | Text/PLCopen import if available; otherwise inspect its supported project format | Installation is not confirmed by the Windows uninstall inventory; inspect separately. Do not substitute it for the DVP-SV3 DIADesigner target |
| Schneider EcoStruxure Machine Expert (M241/M251/M262) | CODESYS-based ScriptEngine, same as `backends/codesys` | Profile name and device IDs |
| CODESYS 3.5 SP22+ | Compare with the official CODESYS MCP Server add-on (needs a Professional Developer Edition licence) | Optional |

The CODESYS-based tools reuse is an assumption until each is run.

## Other candidates (not installed)

Ranked by how often they appear in Indonesian and Asian machine building and by whether an official write path exists.

| Target | Note |
| --- | --- |
| Rockwell Connected Components Workbench (Micro800, free) | Check import/export of ladder |
| Rockwell Studio 5000 (ControlLogix/CompactLogix) | `.L5X` XML import/export is official; licence required |
| Inovance AutoShop (H3U/H5U) / InoProShop (AM/AC) | AutoShop: check IL import. InoProShop is CODESYS-based |
| LS Electric XG5000 (XGB/XGK) | Check IL text import/export |
| Keyence KV Studio (KV-8000/KV-X) | Check mnemonic text import |
| Xinje XDPPro, Panasonic FPWIN GR7 | Check IL/mnemonic import |
| Schneider Control Expert (M340/M580) | XEF/ZEF XML import/export; expensive licence |
| ABB Automation Builder, B&R Automation Studio | CODESYS-based (ABB); B&R: check text/ST import |

## Improvements to existing backends

| Target | Note |
| --- | --- |
| Wider Omron CP1H / CP2E coverage, then CP1L, then CJ2 | Completed in order: CP1H X/XA and CP2E N, CP1L M/L/L10, CJ2M CPU31. All [seven original instruction probes](contoh/omron/cpu-probes/) were generated through MCP, compiled in CX-Programmer 9.75 with 0 errors/0 warnings, saved/reopened/recompiled and matched by fresh saved-CXP MCP read-back. Ready projects and native step GIFs are included; see the [validation record](docs/operations/omron-cpu-validation.md). Other variants, broader instruction coverage, simulator timing and physical tests remain planned. The external backend's local corrections are not bundled without a redistribution license |
| Siemens TIA Portal V21 | Supported by the backend (`runtime/v21`). Not yet run here |
| Sysmac Studio: XML export read-back, `.smc2` export, I/O mapping | XML export is licence-gated on the development machine; read-back currently parses the stored listing |
| Machine Expert - Basic: comparisons, word operations, CTD, more templates | Codec supports bit logic, TON/TOF/TP and CTU only |
| WPLSoft: rung (segment) comments, edge contacts, API instructions, ES2 template | Segment comment record not yet decoded |
| Haiwell: direct `.hwb` block import | File > Import > Program accepts a hand-edited block once its CRC-16/MODBUS section checksums are recomputed (checked on V2.2.13). A full encoder would replace keystroke entry and lift the branch limits |
| Haiwell: more CPU templates, TON 10 ms/100 ms base, nested branches | Keystroke entry supports TON with 1 s base only and one level of parallel branches |
| Demo recordings for Sysmac, Machine Expert - Basic and WPLSoft | Verified by tool output; recordings pending (CODESYS recorded in v0.3.0) |
| Outseal Studio: upload | Deliberately not exposed: it writes to a board |
