# DIADesigner SV3 Backend Implementation Plan

**Historical SV3 plan, not the current release gate.** On 2026-11-03 the user explicitly selected the installed DVP-SS2/WPLSoft route for the current Delta demonstration. That MCP/native example is complete; DIADesigner LD write/readback remains planned. See [current BMAD outcome](../../../_bmad-output/delta-beckhoff-expansion.md) and [ROADMAP](../../../ROADMAP.md). The earlier full-profile-isolation-only prerequisite below is superseded by the repository's owned-session/process/workspace policy, not a requirement for a second account or VM.


> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real offline MCP backend that authors LD for DVP28SV311S through DIADesigner and proves native build and saved-program read-back through multi-plc-agent.

**Architecture:** Keep WPLSoft's existing `delta_mcp` unchanged. Add `backends/diadesigner/diadesigner_mcp/`, registered as backend `diadesigner`, vendor `delta`, prefix `delta_dia_`. Use a vendor-supported exchange or automation path only after a real import/write round-trip establishes compatibility.

**Tech Stack:** Python standard-library stdio MCP, installed DIADesigner 1.15.0.334, Windows runner only if scoped UI Automation and an isolated application fixture are verified. No dependency installation or self-elevation.

**Spec:** `../../../ROADMAP.md`, sections Backend delivery contract and HMI-AI integration boundary.

## Global Constraints

- Primary account remains `wayandadang`; no WSL duplication or required account switch.
- Digital scope: DVP28SV311S. Record the GUI family `DVP28SV3` separately from the exact ordering code and physical output variant.
- No PLC connection, download, online mode, force operations or simulator stimulus writes.
- Preserve `--allow-write`, explicit overwrite permission and backup; reject unsupported instructions and unproved targets.
- Manual seed/setup is interface evidence only. Asking the operator to author the requested ladder is not backend acceptance.
- Do not redistribute vendor manuals, DLLs, installers or vendor sample projects.
- No supported README checkbox or native GIF until the real agent-authored workflow succeeds.

## Review Focus

- Imported POU not assigned to a task: reject apparent success without persisted task evidence.
- Build against the wrong selected controller: bind the build receipt to the requested device/POU.
- Compiled-text export has different structure than rung JSON: compare semantic logic, not the generated input file with itself.
- Model-family selection is not exact hardware verification: preserve both identities without claiming physical PNP validation.
- Import/compile failure after replacement: preserve the original project and report committed side effects; never invent a successful rollback.

## Task 1: Prove the native write/read seam before product code

**Files:** Use local synthetic artifacts under `_scratch/delta-sv3/`; inspect the installed manual locally. Do not add a backend or config entry in this task.

**Interfaces:** Input is the requested model, a scratch destination and rung JSON; no pre-existing POU or operator-authored LD is required. Output is a receipt naming the supported creation/write method, declarations/task representation, native compile operation and independent saved-program read-back method.

- [x] Inspect the installed manual sections 8.2.1.2 (printed pp.219–222), 8.4.2 (p.419), 8.4.3 (p.423), and 19.7 (p.723). Revision history states SV3 support was added in 1.3.0 and the 1.15 compatibility table includes DVP-28SV3; do not compare the older `1.30` spelling numerically with `1.15`.
- [ ] Establish native project/device/POU creation from an empty scratch project through a supported interface or a verified scoped driver. A non-password-protected `.export` may be inspected as optional interface evidence if already available; do not require the operator to create LD or an export to start development. Do not decrypt, decompile vendor binaries, or assume PLCopen compatibility.
- [ ] If there is no documented writable exchange, evaluate a scoped editor driver only after the desktop isolation/access gate passes. A scratch directory and a new process alone do not satisfy that gate. If neither path can be established, stop this workstream as blocked, without a fake or empty backend.
- [ ] Prove the backend can create the scratch project/device/POU and one agent-authored NO-contact/coil LD program, assign it to the intended task, compile, save, reopen and read it back. Preserve native diagnostics and task/declaration read-back. This is a feasibility probe, not full support acceptance.

## Task 2: Implement the complete backend

**Files:** Create `backends/diadesigner/diadesigner_mcp/{__init__.py,__main__.py,server.py,ladder.py,native.py}` and `backends/diadesigner/tests/test_diadesigner.py` only after Task 1 passes.

**Interfaces:** Match existing `Server.call(name: str, args: dict) -> dict` and stdio protocol 2025-06-18. `ladder.validate(rungs: list[dict], aliases: dict[str,str]) -> list[dict]` checks target-specific inputs without writing. `native.run(job: dict) -> dict` returns actual operation diagnostics, target identity and persisted read-back; it does not expose arbitrary commands. Public tools are `validate`, `new_project`, `write_ladder`, `compile`, `read_program`, and read-only discovery.

- [ ] Write and run failing behavioral tests for invalid SV3 addresses, unsupported opcodes/targets, malformed branches, write denial, overwrite refusal, missing task assignment and read-back mismatch. Expected output must be independent of the implementation.
- [ ] Implement validation/serialization using the exact exchange proven in Task 1; no inherited ES2/SS2 limits or assumed CODESYS profile.
- [ ] Implement native operations with target/POU-bound compile diagnostics, explicit backup and bounded failure handling. Propagate missing software/profile and failed vendor operations as tool errors.
- [ ] Run those tests green, then exercise initialization, discovery, validation, denied write and teardown through the actual stdio process. Do not claim GUI/build success from protocol tests.

## Task 3: Router, conveyor, examples and evidence

**Files:** Modify `config.example.json`, README support/detail sections, `ROADMAP.md`, `CHANGELOG.md`; add original artifacts under `contoh/diadesigner/` and a reviewed GIF under `docs/demo/` only after success.

- [ ] Register the real backend with explicit prefix `delta_dia_` so existing WPLSoft `delta_` callers retain their meaning. Exercise it through `Router` rather than only direct Python handlers.
- [ ] Through MCP generate the shared conveyor: start/stop seal-in, simulated E-stop permissive, three-second horn, product counter/reset, stop at ten and batch lamp. Native compile, save/reopen, persisted task/declarations and semantic read-back must all pass.
- [ ] Store original rung input, an English reproducible prompt, exact target/software identity, canonical `signals.csv` and verification evidence. Distinguish build, read-back, simulator and physical test statuses.
- [ ] Record only the real successful tool/native sequence. Inspect/crop every exported frame for privacy; no synthetic GUI or passing overlays. Respect repository media size rules; keep full MP4 local.
- [ ] Update HMI bindings only from the accepted canonical signal source; do not copy WPLSoft mappings or grant write access. Preserve the existing Omron-specific checker rather than pretending it is vendor-generic.
- [ ] Run the relevant behavioral/stdio/router checks and the full existing suite once after integration; perform the real native smoke again after changes affecting the write path. Review changes and secrets before preparing a signed-off commit. Do not push unverified support claims.

## Current Evidence and Handoff

Task 1 remains incomplete. A live, PID/start-time/executable/session-bound read-only probe reached the operator's synthetic scratch window on 2026-11-02. Both agent and editor had Medium integrity (RID 8192). The initial main-window traversal was depth-truncated; the subsequent targeted `SolutionExplorerPanel` traversal completed without truncation and exposed `treeListControl` plus the project/Add Device nodes, with no controller or POU. The actual `BOP_NEWPROJECT`, `BOP_NewDevice`, `BOP_SAVEPROJECT`, `PRG_Compile` and `PRG_ProjectCompile` selectors were observed; compile buttons were disabled. Supported UIA Invoke patterns were observed but never invoked. Probe exit status was 0 and `actionsInvoked` was 0. This proves read access, not creation, writing, build or read-back.

Local reproduction artifacts are under `_scratch/delta-sv3/`: `Inspect-DIADesigner.ps1`, `read-only-probe-20261102.json` and `project-tree-probe-20261102.json`. They are diagnostic artifacts, not a registered MCP backend or publication-ready GIF.

The remaining write gate is an approved, verified isolated application fixture or documented offline write API. A full-text search of the installed user guide found no documented user-profile/data-directory switch; its command-line section concerns CARD Utility, not LD authoring. The scoped installed-file/ProgID checks did not establish a public DIADesigner automation API. These bounded searches do not prove that no API exists. Do not infer profile isolation from readable controls or a scratch project, and do not bypass it by invoking the current personal-profile editor. No operator-authored ladder or export is required. The `.diade` file is not plain XML; compiled-text export is not proof of text import. SV3 simulation remains unverified.

Execution of this plan has been requested. Continue native write operations only after the write gate is met; do not ask for repeated plan approval or produce a fake/empty backend. No backend, native build, GIF, commit or push is claimed by this document.
