# Open Industry Conveyor Pilot Implementation Plan

> Execution: lead-owned, inline, using executing-plans. The operator approved the six implementation stages, dedicated local runtime operation, exact TwinCAT.XAR.PLC=2.4.12 installation and an official TC1200 seven-day trial if needed. The later publication request authorizes committing and publishing this multi-plc-agent feature branch only; no upstream submission, physical PLC connection, automatic reboot, other package upgrade or OS security change is authorized. UAC cancellation is not permission to seek another elevation route; trial security-code verification remains human-only.

**Goal:** Demonstrate one agent-authored conveyor with reproducible behavioral evidence, first in OIP and an open-source external runtime, then on the existing Beckhoff TwinCAT RT (x64) software target if that runtime is available.

**Architecture:** Keep OIP and multi-plc-agent separate. Use OIP's official desktop MCP for scene authoring and readback; keep vendor artifacts here, outside the OIP source repository. Use the source development shell for the owned test profile: its supported unpackaged mode does not run the installed app's auto-updater. Do not patch the installed ASAR.

**Tech stack:** Existing Windows Node 24.15.0; pinned OIP source a7648fc824b3dc260ee69b8965359037048c2698; lockfile-controlled project dependencies; existing TwinCAT engineering installation; existing ffmpeg. New installs require sysinv preflight. OpenPLC is a separate process, not linked into OIP.

**Spec:** Local research report at ../../../_research/open-industry-plc/outputs/oip-plc-integration.md and the operator's six acceptance stages. Source report is a research proposal, not previous runtime evidence.

## Global constraints

- Windows account wayandadang only; owned application profile and scratch workspace, no new Windows account or VM.
- Target is TwinCAT RT (x64), not CX7000/ARM; no physical terminal mapping or physical PLC operation.
- Installed OIP remains unchanged. The development shell must honor redirected profile/project folders and use a dedicated loopback MCP port.
- Preserve the original example 01. Create example 02 only for measured integration artifacts; publish no unearned status, fixture, video or zero-error claim.
- Separate internal IEC simulation, external OpenPLC execution, vendor runtime execution and hardware evidence. Runtime activation/download requires a positively identified dedicated local target and its own safety decision.
- Reuse StartPB, StopNC=healthy TRUE, EStopHealthy=TRUE, PartSensor, CountReset, Horn, Motor and BatchLamp; horn delay 3 s, batch 10, native task 10 ms. The pilot explicitly separates the physical photoeye edge from Motor after reproducing duplicate counting across restart. It has eight LD rungs, 14 ordinary variables and two function-block instances. Canonical bindings use MAIN.*; original example 01 is preserved and its limitation documented.
- Test records use English. Chat explanation remains Indonesian. No licensed binaries, credentials or proprietary libraries committed.

## Review focus

1. STOP/E-stop during the horn delay must cancel the request; recovery must not invent a fresh start edge.
2. A held sensor counts once, not once per scan; a stuck sensor/jam must fail a process assertion or reach a documented timeout.
3. Loss of an external link cannot leave stale values looking valid; a stopped runtime that still serves requests is not healthy execution.
4. The physical box position/zone must agree with the motor trace; a boolean-only test is insufficient.
5. Failure of an external runtime cannot silently fall back to the internal engine and retain a vendor PASS verdict.

## Task 1 — Real desktop MCP and saved scratch readback

Files: example 02 runner/evidence and owned scratch profile; OIP source stays standard unless a reproduced feature defect requires a focused fix.

- [x] Install only preflight-approved lockfile dependencies; suppress lifecycle hooks and separately review the required pinned Electron download hook. Existing Node 24.15.0 was reused; Electron 42.11.10 is a project development dependency.
- [x] Launch a Windows source development shell and loopback UI server with an owned profile/project root. Unpackaged mode does not run the installed application's updater; the installed ASAR is unchanged.
- [x] Initialize actual MCP, discover 58 tools, create/write a scratch project and independently read both MCP state and saved project files.
- [x] Capture the actual owned renderer over CDP. The optional MCP capture_view returned UnknownVizError; do not claim that tool passed. No personal window or second Windows account was used.

## Task 2 — Conveyor with red/green process acceptance

Files: contoh/beckhoff/02-oip-conveyor/contract.json, simulation project and test specifications, native request, replay runner.

- [x] Observe the initial missing-controller acceptance fail, then pass after agent authoring.
- [x] Author the conveyor, metered source, mounted controls, photoeye, tracked box and destination through MCP; no hand-written scene.json.
- [x] Verify horn timing, start/stop, E-stop, physical sensor edges and batch behavior with actual world probes.
- [x] Run nine saved scenarios / 54 checks, including sensor-stuck, physical jam, safe-off I/O communication loss and recovery; keep their internal-engine scope explicit.
- [x] Remove the E-stop interlock in a separate project; motor and physical-position assertions reject it. The positive saved source hash remains unchanged.

## Task 3 — Open-source external runtime

- [x] Discover no registered/default OpenPLC installation or API listener. Identify official native Windows Runtime v4.3.2 (228075658-byte installer, published SHA-256); installer sysinv preflight returned 0. Docker was not used.
- [x] Obtain exact operator approval; install official native Windows Runtime v4.3.2 per user without admin elevation. Verify 228075658-byte download SHA-256 before execution; preserve the installation log.
- [x] Initialize a fresh private local SQLite/account, with credentials ACL-restricted outside the repositories; constrain Python listeners to loopback. All nine original scenarios / 54 checks passed on the real PLC wall clock and Modbus TCP: 37,945 actual requests, zero protocol exceptions. Preserve actual program identity, tag traces, world probes and compiler receipts. The published portable runner separately passed complete physical-transfer and held-photoeye-regression smokes.

## Task 4 — One Beckhoff runtime

- [x] Initially read local ADS states only: system port 10000 Config (15), PLC 851 code 6. After the operator's explicit permission, target all runtime actions only at the separately owned usermode identity, never the kernel-local identity.
- [x] Inspect installed packages and host virtualization. UserModeRuntime 1.27.1 and Base.UM are installed; Hyper-V is present. Normal PLC execution licensing remains a separate requirement; the shared license directory is empty.
- [x] Create/read back/build the dedicated eight-rung LD through actual multi-plc-agent MCP. Write and independent rebuild report 0 errors / 0 warnings / 0 failed projects; fresh exported logic, 16 declarations and task binding match. All owned native hosts exited; online_operations=0.
- [x] Obtain permission for a dedicated local usermode instance and native boot load/run. Copy/hash-verify twelve native-generated boot files only into its private profile. Do not expose online operations in the offline MCP backend.
- [x] Obtain separate operator approval for exact TwinCAT.XAR.PLC=2.4.12 and an official TC1200 trial. The package plan is UM-compatible, requires admin and declares no service restart/test mode/hardware requirement. The normal elevation attempt was canceled by Windows before the elevated script started; no package was installed and no alternate elevation route was attempted.
- [x] Rebuild the private clone in a fresh owned XAE host; LastBuildInfo=0. Public-SDK ActivateConfiguration and StartRestartTwinCAT returned for the exact owned usermode NetId, but ADS 851 still returned code 6. Preserve the actual target fatal dialog: “license not found”. Acknowledge that recorded error; do not mistake command return for RUN or infer an additional missing-driver cause.
- [x] Preserve the initial operator cancellation. On the later explicit retry request, follow the manual licensing route, leave automatic detection enabled and identify TC1200 / TC3 PLC as the only missing product. The operator personally completes the security-code input/submission; a normal response appears under the private target's Target/License. Do not publish the license payload, device identifier or challenge image.
- [x] Activate/restart only the guarded owned usermode target after licensing. Both system 10000 and PLC 851 report RUN (5); actual MAIN declarations match, and compiled/active boot-app digests are identical. All nine original wall-clock scenarios / 54 checks pass over native ADS and real Jolt physics. Independent final reads verify Motor/Horn/RunReq/BatchLamp FALSE and counter zero. Kernel-local system remains CONFIG (15).
- [x] Preserve the first native transfer smoke's two timing misses and its 3.783 s motor transition. A no-physics timer probe also measures wall-clock drift. No controller, task or canonical assertion was relaxed; finite success is not deterministic timing.
- [x] Reproduce the ADS runner exit bug on the real PLC: active Motor/RunReq and count 3 remain after process return. Add stop/reset and bounded native postcondition verification; the same actual regression passes afterward. Also start the native motor, force a post-bind invalid-case-selection error and independently verify inactive motor/horn/run request and counter zero on the nonzero exit.

## Task 5 — Actual recording and documentation

- [x] Record the actual successful live internal-engine batch; encode/review every exported GIF frame (154) and inspect the full MP4 preview. Recordings are scope-watermarked, not a claim of vendor runtime execution.
- [x] Include native/source/scene hashes, actual assertions and traces, Node/Electron versions and engine identity.
- [x] Update English example documentation, README indices and changelog. Actual packaged MCP replay recreated a scene, passed 9/9 scenarios and 54/54 checks, and rejected the mutant. Final repository regression: 265 passed, 3 skipped, 24 subtests passed in 25.13 s. After the ADS cleanup correction, an actual OpenPLC compile/transfer smoke still passes 9/9 checks and the runtime is independently read as STOPPED. Strict scene validation passes; all 51 pinned files / 30 JSON documents verify with zero digest mismatches.
- [x] The measurement stage made no commit, push, upstream issue/PR, new-driver installation, kernel-runtime configuration or physical PLC operation. Only the explicitly approved official trial was activated by the operator; publication was separately authorized afterward.
- [x] After completion, the operator confirms intentionally closing the desktop/runtime. Preserve exit code 84 and absent-process/ADS observations as a post-test shutdown, not a new scenario failure. Saved passing results remain historical; no restart or new trial action is needed unless the operator wants another replay.
- [x] Pre-publication review traced upstream RuntimeClient.login first-account provisioning. A bounded probe blocked the attempted create-user request before HTTP; the corrected runner refused it without create-user or stop requests. Real existing-account compilation and transfer still passed all nine smoke checks; no account was created.

## Readiness

PASS for the scoped functional pilot: desktop MCP, native engineering, internal physics/negative control, actual internal recording and all nine scenarios on each real external runtime are proved. CONCERNS remain: Usermode has no deterministic timing guarantee, the earlier native deadline miss is retained, and physical I/O/CX7000/ARM/hardware were not tested. The installed OIP app is untouched; no extra Windows account, VM, kernel configuration, driver or Windows-security change was performed. The canceled component installation was not needed for the successful licensed run.

## Execution rulings and evidence

- Ruling: use the official source development shell rather than patching installed app.asar; unpackaged updater behavior is documented. Cost: project-local development dependencies were required and preflighted.
- Ruling: use actual CDP capture after capture_view failed; do not turn the failed optional tool into a hidden success claim.
- Ruling: fix only the new pilot's sensor-edge implementation and document the original six-rung limitation; do not invalidate or rewrite historical native engineering receipts.
- Actual regression: held photoeye across motor restart counted 2 instead of 1. Independent edge memory fixed the same check; native eight-rung source separately built and read back.
- Actual process defect: the initial scene dropped two boxes beyond the belt. A real destination part removed the spill; the zero-floor-cargo assertion passed afterward.
- Canonical tests live only in simulation/tests and its manifest; obsolete authoring copies were removed.
- The independently invoked standalone project validator accepted the portable 13-part project and all six bundled part copies. Its physics CLI also passed all nine canonical tests / 54 checks. The jam trace additionally reported a 17 ms photoeye flicker; missing debounce and unverified physical-item counting under chatter are explicit example limitations, not suppressed observations.
- Native raw receipts, original failed cases, live trace and local full MP4 remain in the separate research pilot workspace. Sanitized receipts, source and reviewed GIF are in example 02.
- Permission boundary: compiler text “Ready for download” is not a receipt. Native execution is now evidenced separately by guarded SDK activation, actual RUN/symbol reads, matching compiled/active app digests and complete ADS world/probe traces; hardware execution is not inferred.
- The runtime adapter requires explicit local-lab targeting and write consent. It neither bootstraps accounts nor installs dependencies, licenses or vendor configurations. Both external paths are measured; ADS shutdown additionally verifies inactive commands and counter zero before closing.
- Runtime readiness does not follow from an ADS command acknowledgement. Unsupported ADS RUN (0x701), pipe-launched console input and RUN-to-CONFIG reversion are retained as failed attempts, not hidden by a success summary.
