# Repository engineering policy

Read CONTRIBUTING.md and ROADMAP.md before changing PLC support. Operational evidence for the new TwinCAT adapter is in docs/operations/beckhoff-native-validation.md; Omron evidence remains in docs/operations/omron-cpu-validation.md.

- This repository routes vendor-specific offline engineering MCP backends. A manual LD tutorial, generated input alone or model-written success summary is not a working backend.
- Native write/build plus matching independently read saved logic is the engineering acceptance gate. Simulation, Factory I/O and physical PLC testing are separate evidence levels, not unconditional commit/publication prerequisites. Never claim them from compilation.
- Current Beckhoff acceptance is TwinCAT RT x64, not CX7000/ARM or physical I/O. Select the offline engineering platform explicitly; IDE-local active configuration is not portable source state. Do not activate configurations or change runtime modes.
- The shared IEC LD codec is multiplc.iec_ld. Keep CODESYS and TwinCAT on that one implementation; migrate callers rather than adding aliases/copies. Source-only backend launches need the checkout root on PYTHONPATH.
- Preserve write opt-in, trusted workspace bounds and explicit overwrite with backups. Open only fresh owned native hosts; do not attach to personal solutions, kill by process name, require a second Windows account/VM, or invent a blanket profile-isolation release gate.
- Keep compiler counts, failed-project counts, task/declaration/readback matches, simulation and hardware results separate. Unknown counts are not zero. Export success alone is not persistence proof.
- Delta WPLSoft is supported. DIADesigner SV3 remains unverified for native LD write/readback; do not advertise a stub, ask for operator-drawn seed ladder, decode protected formats or reuse WPLSoft words as SV3 source.
- No proprietary DLL/library/installer/manual redistribution or private vendor implementation decompilation. Local SDK bindings are generated against the operator's installed public components.
- HMI-AI and Content Studio are separate consumers. PLC logic/signals/evidence stay canonical here; do not guess live bindings, grant PLC write access, publish private sibling repositories or reschedule content as a side effect.
- New public examples, backend docs and receipts are English. Review every native recording frame for private data and label step captures versus continuous recordings accurately.
- Regression command: python3 -m pytest tests backends -q. Run the actual changed native path as well; tests alone do not establish vendor acceptance.
- The capability-adapted teaching catalog is contoh/README.md; operational evidence and exclusions are in docs/operations/cross-vendor-examples.md. Cases 01/02/07 have native acceptance on seven backends; Siemens 03/04 are LAD/SCL hybrids. New-target XY-MD02 and Sysmac task-bound examples remain unchecked, not implicit support.
