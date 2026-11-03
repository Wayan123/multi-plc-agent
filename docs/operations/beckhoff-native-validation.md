# Beckhoff native engineering validation

Date: 2026-11-03. Scope: original multi-plc-agent Beckhoff MCP adapter, **TwinCAT RT (x64)** offline engineering. See [backend setup](../../backends/beckhoff/) and [the reproducible native example](../../contoh/beckhoff/01-twincat-rt-x64-conveyor/).

## Observed results

| Gate | Result |
| --- | --- |
| Actual router discovery and native write | Passed; six LD rungs, nine BOOL declarations plus TON/CTU |
| Save, close and reopen | Passed; MAIN is called by cyclic PlcTask, 10000 us |
| Native compiler/build | 0 errors, 0 warnings, 0 failed projects |
| Independent export and fresh-host rebuild | Passed in two further native hosts; all requested logic/declarations/task binding match |
| Owned-host cleanup | All three acceptance hosts exited; no online operation was invoked |
| Cold source-only project | Passed build/readback without shipping .vs state, TMC, compiler caches or vendor libraries |
| Access boundaries | Actual MCP write denial without --allow-write and out-of-workspace read denial; no denied destination created |
| Repository regression suite | `python3 -m pytest tests backends -q`: 230 passed, 3 skipped, 24 subtests passed |
| Existing cross-project references | Seven Omron examples, HMI-AI and Content Studio indices, HMI bindings: passed |
| Native visual evidence | Two actual owned-window step captures; every exported GIF frame reviewed |
| Simulation / Factory I/O / physical PLC / CX7000 | Not tested; not prerequisites for this accurately scoped engineering claim |

The public [native-evidence.json](../../contoh/beckhoff/01-twincat-rt-x64-conveyor/native-evidence.json) is derived from actual router responses. Raw captures, SDK probes and machine-specific receipts stay local. No API key, proprietary assembly, vendor library binary, installer or manual is included.

## Important native findings

1. **Use typed public SDK bindings.** Late-bound Python COM marshaling failed for some DTE2/virtual IEC interfaces. Original C# against the installed public type library works. This is not evidence that vendor interfaces are absent.
2. **Resolve standard libraries first.** After sysinv preflight, feed dry-run and explicit owner approval, only Tc2_Standard 3.4.7, Tc2_System 3.10.2 and Tc3_Module 3.4.7 packages were installed. The initial E_FAIL was accompanied by unresolved references; native build succeeded after their resolution. Do not install an invented rollup package or duplicate toolchain.
3. **Import accepted does not mean saved.** A replacement was correct in memory but disappeared after SaveAll/parent Save/Close(true). Native removal of only the backed-up owned MAIN before import made the program persist. The production writer creates a fresh project and performs this public-API cutover, then verifies after reopen. Whole-project overwrite preserves an unused sibling .bak directory.
4. **Choose the platform on every operation.** Active XAE platform state is not portable in source-only files. A cold copy opened as TwinCAT OS (x64). Selecting TwinCAT RT (x64) explicitly through ConfigurationManager before build/export fixed the reproduced failure; cold native build/readback then passed. This is engineering configuration selection, not ActivateConfiguration or a runtime mode change.
5. **Keep evidence levels separate.** An absent compiler count is unknown, not zero. Failed-project count is not diagnostic-error count. A matched PLCopen export is not execution, physical stopping, I/O commissioning or functional-safety proof. Standard-template compiler settings are retained.
6. **No account/VM gate.** The existing authorized Windows account and fresh owned native hosts suffice for this measured workflow. They do not isolate shared installation/registry/UI settings. Never attach to or close a personal open solution.

## Reproduce

- Use the exact rung request and MCP sequence in the example README; no manual ladder entry is needed.
- Set a dedicated trusted workspace and explicit --allow-write only when authoring.
- Require real native diagnostics and matching LD/declarations/task binding after reopen; export/build again in fresh hosts.
- Do not activate configurations, start runtimes, connect/download/force, or infer hardware addresses.
- Review every visual/text artifact before publication. The two-frame GIF is a step capture, not a continuous authoring video or simulation.

## Delta disposition

DIADesigner 1.15.0.334 contains the DVP28SV3 catalog entry. The agent created/saved a project and assigned an LD POU to Freewheeling (0), then saved a real 2785-byte native .export with Password Setting unchecked. Its SHA-256 is d96163ec19afbd1d4bee05b3a8406b5222081f1d007a3b617755d7298192e243. It is binary, not a standard ZIP/PLCopen XML container; this does not prove encryption or incompatibility.

The inspected canvas has no individually exposed placement nodes. Toolbar actions have not established an authored rung or independent semantic readback. Targeted installed SDK/type-library filename and registered-public-type-library checks found no matching engineering interface; public searches did not establish a supported automation API. These bounded checks do not prove no API can exist. No private vendor implementation was decompiled or decrypted. DIADesigner remains unchecked; the existing WPLSoft adapter is unchanged.

## Review limits

Runtime timing/scan behavior, safety, physical PLCs, CX7000/ARM, alternate XAE/VS editions, vendor SDK security and deadline/cancellation failure injection were not tested. HMI-AI remains read-only; there is no new ADS/live binding or native HMI writer. No independent model/subagent review is claimed.
