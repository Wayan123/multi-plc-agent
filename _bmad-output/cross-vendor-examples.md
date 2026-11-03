# BMAD execution record: capability-adapted teaching cases

## Brief / decision

Extend the seven original Omron teaching topics to feasible existing PLC backends. The operator approved real-capability adaptation rather than artificial feature parity: unavailable analog/Modbus/target combinations remain visibly unchecked. English public artifacts; MCP-authored source; native compiler and independent saved readback are the engineering gate. Simulation and hardware remain separate.

## Architecture / implementation

- Canonical digital behavior and lowering: contoh/teaching_cases.py. Existing vendor schemas and shared multiplc.iec_ld are reused; no parallel codec or compatibility shim.
- Cases 01/02/07 accepted on Siemens, Outseal, Haiwell, Delta WPLSoft, Schneider M221, CODESYS and Beckhoff. Siemens source is honest LAD/SCL hybrid.
- Siemens 03/04 have real offline four-AI/two-AO module configuration, clamped raw commands and DINT input/output scaling.
- Each accepted folder contains original reusable source, native project or actual vendor readback, English instructions, read-only signals, actual sanitized evidence and SHA-256 inventory.
- New-target XY-MD02 05/06 and task-unbound Sysmac remain unchecked; incomplete native probes were kept private, not published as scaffolds.

## Verification / review

Native measurements, failures/recoveries, exact evidence boundaries and software versions are recorded once in [the operational runbook](../docs/operations/cross-vendor-examples.md), with original per-case receipts linked by [the catalog](../contoh/README.md). Digital model regression is tests/test_teaching_cases.py; it is not a vendor simulator. No independent model/subagent review is claimed. Final local/CI verification must be reported from actual command output, not this design record.

## Delivery contract

Preserve the existing seven Omron manifests and sibling consumer pins. Do not stage native user .opt sidecars, private paths/configuration, vendor binaries/libraries or recordings not actually made. Publish only reviewed/scanned source through a signed, DCO-signed-off feature-branch commit and PR; do not merge protected main automatically.
