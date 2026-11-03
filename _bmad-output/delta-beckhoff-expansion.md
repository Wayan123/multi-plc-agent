# Delta and Beckhoff MCP expansion

Date: 2026-11-03. Track: resume the existing Build plans with a technical readiness gate and correct-course target selection.

## Authorized outcome

Provide real offline LD engineering through the multi-plc-agent router for Delta and Beckhoff. The user permits choosing the easiest PLC target compatible with the installed engineering software. Do not ask the operator to draw LD manually. Use the existing Windows account and owned synthetic projects; no account/VM prerequisite. Separate accounts do not isolate machine-wide components.

Native compile and matching vendor readback establish engineering acceptance only. Simulation and physical PLC tests are separate claims, not mandatory publication gates. No connect, activate-configuration, runtime-start, download, force, or physical I/O operation is authorized.

## Selected initial targets

- Delta final target: **DVP-SS2 through installed WPLSoft 2.52**, explicitly selected by the user after reviewing the SV3 seam findings. Reuse the existing `delta_` MCP backend and create a new original native example; do not advertise a new DIADesigner backend. The earlier DVP28SV3 investigation remains recorded below and unchecked.
- Beckhoff: TwinCAT 3 software PLC, platform `TwinCAT RT (x64)`, for offline engineering acceptance. This is not CX7000 ARMV7-M support and does not establish physical I/O configuration or a runnable licensed runtime.

## Architecture retained from the existing plans

- Delta DIADesigner: original stdio backend `diadesigner`, vendor `delta`, router prefix `delta_dia_`; preserve the existing WPLSoft backend and `delta_` tools.
- TwinCAT: original stdio backend `twincat`, vendor `beckhoff`, router prefix `beckhoff_`; use the public Automation Interface and vendor-supported import/export.
- Reuse rung JSON and the repository's write opt-in, backup, validation, native diagnostics, and independent readback conventions. Share IEC serialization only after actual TwinCAT import/export proves compatibility. Do not copy a second CODESYS backend or expose a general COM/shell executor.
- HMI-AI remains a separate read-only consumer. PLC support does not imply a native HMI writer, working live transport, or verified signal addresses. No unrelated HMI or content-studio publication.
- No proprietary binary reverse engineering, decryption, vendor DLL redistribution, or copying vendor manuals into the public repository.

## Acceptance stories

1. Agent creates a fresh native project and the required device/POU/task binding.
2. A minimal contact/coil LD round-trip first proves the writable native seam.
3. MCP validates and authors the shared conveyor example: start/stop seal-in, permissive input, 3-second timer with horn, counter preset 10/reset, and batch lamp.
4. Vendor build is actually executed; retain native diagnostics, source identity, and task/platform evidence. A project-failure count is not an error-message count.
5. Save, close, reopen, and independently read/export native logic; compare semantic logic, declarations, parameters, and task binding with the request.
6. Exercise the public router, write-denial/overwrite behavior, meaningful boundary tests, and regression suite. Only then update support checkboxes and create GIF evidence from the real successful native surface.

## Observed installed environment

Read-only registry inventory, 2026-11-03: Windows account `wayandadang`, input desktop `Default`; DIADesigner 1.15.0.334, WPLSoft 2.52, TwinCAT XAE Shell 64-bit 9.0.2.0, TwinCAT PLC integration 7.1.3 / native 4026.27.4.0, both TcXaeShell64 and VS2022 integrations. ISPSoft was not found in the inspected installed-application registry views. The owner subsequently explicitly authorized the three minimal Beckhoff libraries below; no other package or system configuration was changed.

## Native readiness and measured outcomes

- Typed C# bindings against the installed public SDK access DTE2 diagnostics and the virtual IEC project/task tree. Python late-bound marshaling failures were a client-binding limitation, not absent vendor APIs. No private implementation was decompiled.
- The initial empty-project E_FAIL was accompanied by three unresolved standard libraries. After a clean sysinv preflight, reviewed Stable Feed dry-run and explicit owner authorization, the exact packages `TwinCAT.XAE.PLC.Lib.Tc2_Standard=3.4.7`, `TwinCAT.XAE.PLC.Lib.Tc2_System=3.10.2`, and `TwinCAT.XAE.PLC.Lib.Tc3_Module=3.4.7` were installed. Native SDK readback resolves them to 3.4.7.0, 3.10.2.0 and 3.4.7.0; Tc3_GlobalTypes resolves to 1.0.0.0. No reboot, service activation or runtime operation was performed. Do not recommend the nonexistent rollup `TwinCAT.XAE.PLC.Lib`.
- A first native LD contact/coil import built with 0 errors and 0 warnings and matched independent vendor export. The full six-rung conveyor subsequently compiled, but an in-memory replacement was initially lost on reopen despite SaveAll/parent Save/Close(true). A successful import call or compiler result alone is therefore insufficient.
- Replacing only the backed-up owned MAIN through the public native tree API made the full conveyor persist. The production writer instead creates a fresh native solution and removes the owned standard-template MAIN before import; explicit overwrite preserves the entire prior owned project in a sibling `.bak` directory. There is no compatibility shim or private file-format writer.
- Fresh templates initially selected TwinCAT OS (x64), even though earlier scratch projects used RT. The production writer now explicitly selects the public ConfigurationManager's `TwinCAT RT (x64)` platform and checks the reopened configuration and actual build output. It does not infer platform identity from installed labels.
- **Real router acceptance:** `beckhoff_write_ladder`, `beckhoff_export_pou`, and `beckhoff_build` ran through multi-plc-agent in three fresh native hosts. Write and rebuild report native 0 errors, 0 warnings and 0 failed projects. All six rungs, eleven declarations (nine BOOLs, TON and CTU), and MAIN -> PlcTask / Cyclic / 10000 us match. The start/stop seal-in includes a batch-complete inhibit, so the example specification stops at ten products. All three owned native hosts exited. Raw receipt: `_scratch/twincat-20261103/mcp-acceptance-101951/verified-native-router-receipt.json`.
- A cold source-only copy exposed IDE-local active-platform state: it opened as TwinCAT OS x64. Every native operation now selects RT x64 through the public ConfigurationManager; the fresh copy then built/read back successfully without bundled `.vs`, TMC, compiler caches or libraries. Actual MCP write-denial and workspace-escape denial also passed.
- Local delivery includes the original source-only native example, reusable request, sanitized receipt/source pins, English setup/operations docs and a two-frame native step GIF. Every exported frame was reviewed; it is not a continuous recording or simulation.
- Full regression command reports 230 passed, 3 skipped and 24 subtests passed. Existing Omron/HMI-AI/Content Studio synchronization passes for seven examples and two consumer indices. Gitleaks scanned the exact 35-file public-source snapshot and reported no leaks. No independent model/subagent review is claimed.
- **Delta:** the agent created and saved its own DVP28SV3 project and MAIN_Digital LD POU assigned to Freewheeling (0). It opened the real POU Export dialog, kept Password Setting unchecked, selected only Programs/MAIN_Digital, and saved a genuine 2785-byte `.export` artifact (SHA-256 `d96163ec19afbd1d4bee05b3a8406b5222081f1d007a3b617755d7298192e243`). The artifact is binary, not UTF-8/XML or a standard ZIP container; this does not establish that it is encrypted or incompatible. No private decoder, decryption or renamed project file is used.
- The owned Delta LD canvas exposes a keyboard-focusable CanvasScroll container but no individual placement nodes. Native contact/block toolbar actions have not yet produced a confirmed authored rung or accessible operand editor. The official manual documents position selection and typed instructions, including `A` for NO and `B` for NC, but a reliable agent-selectable placement seam and independent semantic readback remain unproven. Do not substitute blind canvas coordinates, automatic keyboard fallback, or operator-drawn seed LD.
- **Approved Delta completion:** actual `delta_validate`, `delta_new_project` (SS2), `delta_write_ladder`, `delta_read_il` and fresh `delta_compile` calls ran through the router. Seven rungs were saved natively; all 22 IL entries including END and eleven aliases match. Native check reports 0 grammar errors and Diagram is complete; separate warning count is unavailable. The owned WPLSoft 2.52.0.0 GUI displays the full LD and IL with Compiling is complete. A two-frame reviewed native GIF and source-pinned original example are included. No manual rung entry, new target-family claim, simulation or hardware test.

Raw probes, process manifests and diagnostics remain local under `_scratch/twincat-20261103/` and `_scratch/delta-diadesigner-20261103/`. Fresh-process tests use the existing authorized account; the former profile-isolation-only block is not a project-wide prerequisite.

## Remaining delivery work

- Beckhoff and the user-approved Delta WPLSoft case are complete locally: actual native router acceptance, reusable examples, reviewed step GIFs and English documentation. Review the final publication snapshot and CI before reporting publication.
- DIADesigner SV3 remains planned; it is not required for the explicitly approved SS2 deliverable and no placeholder adapter is included.
- HMI-AI remains a read-only consumer; no guessed hardware bindings or live transport claims.

## Current support disposition

Beckhoff's bounded RT x64 support is checked from actual native MCP acceptance. Delta WPLSoft remains checked with the new SS2 example; DIADesigner/SV3 and CX7000 remain unchecked. No simulation, physical operation or functional-safety claim is made. Both real native step GIFs are included locally; commit/PR delivery is the remaining phase.
