# Cross-vendor teaching example validation — 2026-11-03

## Acceptance and scope

Observed native engineering acceptance is recorded for 23 new examples in [the canonical catalog](../../contoh/README.md). Every checked catalog cell has original source, an actual vendor compilation result and saved native readback. This is not a claim of simulation, sensor communication, commissioning or physical hardware. No new backend, installation, VM or second Windows account was required. Existing dialects were reused; CODESYS/TwinCAT still share multiplc.iec_ld.

The operator explicitly selected capability-adapted scope. New-target XY-MD02, analog combinations lacking a verified channel/instruction fixture and task-unbound Sysmac are unchecked, not generated as fake examples. Existing Omron cases and consumer pins were not changed.

## Observed native results

| Tool / target | New cases | Observed native result | Saved readback basis |
| --- | --- | --- | --- |
| Outseal Studio 3.6 Beta5, Nano V5 / Mega V3 | 01, 02, 07 | Test: 0 errors; fresh HEX observed; no separate warning-count claim | Reopened native project main/initial instructions, aliases and board |
| Haiwell Happy 2.2.13.240603, AT16S0T/P | 01, 02, 07 | 0 errors / 0 warnings | Complete saved IL; cold reopen and compile for all three |
| Delta WPLSoft 2.52, SS2 | 01, 02, 07 | 0 grammar errors; warning count unavailable | Native IL and aliases after fresh open/compile |
| Machine Expert - Basic, TM221M16R/G | 01, 02, 07 | No error status, LD conversion saved; no separate warning-count claim | Complete persisted IL; raw UI-only verdict kept separate |
| CODESYS V3.5 SP21, Control Win x64 | 01, 02, 07 | Fresh build: 0 errors / 0 warnings | Reopened native project, exported LD; generated MainTask calls PLC_PRG |
| TwinCAT XAE 4026.27 / PLC 7.1.3, RT x64 | 01, 02, 07 | 0 errors / 0 warnings / 0 failed projects | Fresh owned native hosts, LD/declarations and MAIN/10 ms PlcTask |
| TIA Portal V20, CPU 1212C V4.7 | 01, 02, 07 | Fresh-open software compile: 0 errors / 0 warnings | Actual LAD FC readback, SCL helper/cycle and independently exported OB1 call |
| TIA Portal V20, CPU 1212C V4.2 + SM1231 AI4 + SM1232 AQ2 | 03, 04 | Fresh-open software: 0 errors / 0 warnings; hardware: 0 errors / 1 protection-level warning | Saved SCL cycle, native OB1 export and discovered module I/O addresses |

Per-case native-evidence.json preserves the detailed sanitized results. Counts from one stage are never substituted for another stage. Source-files.json pins the exact delivered source, native artifact/readback, instructions, signals and receipt. Original private failed probes are not redistributed as ready examples.

## Failures, recoveries and limits

- **Outseal cold startup:** initial metroWindow lookup failed. An explicitly owned prestarted host was observed UIA-ready; all three actual compilations/readbacks then passed. No production driver fix or general cold-start reliability claim was made. The owned host was closed without saving unrelated state.
- **Haiwell traffic timeout:** a local router configuration used timeout instead of the supported timeout_s, leaving a 600 s default. The 52-rung writer outlived its reply. It was not killed or duplicated. After the owned worker naturally finished, native export matched all 168 expected IL instructions. The original GUI was closed without saving, then the files were cold reopened and compiled/read back again. All passed. Reproduction uses timeout_s=1200. A lost RPC reply itself is not a successful write receipt.
- **Schneider readback:** UI aliases differ from physical operand spelling; the digital cases resolve against actual saved symbols. The large traffic editor virtualizes rows, so the raw UI-only match remains false. Complete independently read native saved-file IL matches; no false UI pass was manufactured.
- **TIA V20 documents:** the accepted pattern is LAD FCs plus SCL timer/cycle helpers, as in the existing repository demonstration. S7_Version SD metadata and comments within SD NETWORKs caused real import failures; removing only the rejected template material produced native success. Pure-LAD timer FB probes were not delivered.
- **TIA OB1 reader defect:** DescribeBlockLogic labels an FC-call-only LAD network empty. An actual vendor SD export independently shows the CallCase/AnalogCycle call. The exported document, not the misleading empty summary, establishes the call chain. This tool discrepancy was reported.
- **TIA module verifier defect:** PlugDeviceItem returned VerifyFailed after actual successful module insertion; the rack tree and module I/O addresses independently confirmed it. No duplicate insertion was attempted. GetDevicePlugLocations also omitted occupied entries although slots ceased being free. This discrepancy was reported.
- **TIA analog fixture:** an initial V4.7 hardware compile failed because confidential-configuration password/certificate setup was absent. The passing replacement is explicitly configured V4.2, not a claimed firmware observation from a controller. Its one unconfigured-protection warning is retained. Neither fixture is a deployment recipe. Electrical channel measurement ranges/diagnostics were not independently validated.
- **Sysmac:** real XML import, native 0/0 build and matching saved five-rung LD were observed, after exact native UIA model selection bypassed a failed existing combo lookup. The saved task had no program assignment. Therefore no runnable Sysmac example is published. The owned project was closed; prior backend scope is not expanded by this probe.

## Behavior and safety boundary

Digital examples require a released start before arming, with no held-start restart after a permissive loss. Traffic uses eight phase timers, captures transitions before writes, and provides fourteen separately addressed lamp commands. Corrupt simultaneous phases suppress green/yellow in the scan model; this is not evidence of liveness recovery or physical fail-safety. Only the Outseal Mega V3 fixture has fourteen output addresses; other new traffic examples explicitly use logical/internal signals.

Siemens analog scaling uses signed DINT intermediates, clamping and integer division toward zero. Numeric raw +/-27648 and EU +/-1000 are explicit example assumptions. Verify real electrical range, wiring, quality flags, polarity and protection before equipment use.

No PLC connection/download/upload, force operation, runtime activation, package installation or production safety-setting change was performed for these examples. No new native GIF, continuous video, vendor-simulator trace or physical measurement is claimed. HMI-AI/Content Studio receive no new runtime permissions or guessed live bindings; signals.csv is read-only metadata.

## Local regression and consumer checks

- `python3 -m pytest tests backends -q`: 265 passed, 3 skipped, 24 subtests passed.
- `contoh/omron/check_sync.py` with the existing HMI-AI and Content Studio indices and HMI bindings: seven canonical Omron examples, two consumer indices and read-only HMI bindings passed. No sibling consumer files or existing canonical hashes were changed.
- Dependencies, runtime interfaces and backend implementation code were not changed by this example batch. Native runs above are the smoke evidence; model tests do not replace them.
