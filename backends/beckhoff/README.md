# Beckhoff TwinCAT offline LD backend

Original stdio MCP backend using the installed **public TwinCAT Automation Interface**. It does not use the CODESYS ScriptEngine, decode private vendor binaries, or bundle vendor assemblies.

## Verified scope

- TwinCAT XAE Shell 64-bit 9.0.2.0, PLC integration package 7.1.3 / engineering build 4026.27.
- Platform **TwinCAT RT (x64)**; `MAIN` is assigned to cyclic `PlcTask`, 10 ms.
- Shared conveyor: seal-in start/stop, E-stop status permissive, 3-second horn/start delay, motor, counter preset 10 with independent reset, stop at ten and batch lamp.
- Actual router write, save/close/reopen, native compile **0 errors / 0 warnings**, fresh-host export and fresh-host rebuild. LD, declarations and task binding match the request.
- A cold source-only copy also builds and reads back correctly without bundled libraries, TMC, compiler caches or IDE state. Actual MCP write-denial and workspace-escape denial were exercised.
- **Not verified:** CX7000/ARM targets, physical I/O mapping, ADS transport, runtime execution, Factory I/O, simulation or hardware. This is ordinary control logic, not a certified safety function.

See the [ready example, native source, receipts and reviewed GIF](../../contoh/beckhoff/01-twincat-rt-x64-conveyor/).
Operational findings and regression results: [native validation record](../../docs/operations/beckhoff-native-validation.md).


## Prerequisites

Use an existing licensed Windows XAE installation and the current authorized Windows account. No second account or VM is required. This backend starts a **fresh visible owned XAE Shell** per native operation and closes only that host; it never attaches to a personal open solution. UI/MRU state may be shared by the application.
Every native operation explicitly selects the **offline RT x64 engineering configuration** through the public ConfigurationManager. A cold solution may otherwise inherit TwinCAT OS (x64) from IDE-local state. This does not activate a configuration or change any runtime mode.


The tested installation provides:

- Registered `TcXaeShell.DTE.17.0` and the installed standard PLC/project templates.
- Resolved `Tc2_Standard` 3.4.7.0, `Tc2_System` 3.10.2.0, `Tc3_Module` 3.4.7.0 and `Tc3_GlobalTypes` 1.0.0.0. Their minimal package IDs are `TwinCAT.XAE.PLC.Lib.Tc2_Standard`, `TwinCAT.XAE.PLC.Lib.Tc2_System` and `TwinCAT.XAE.PLC.Lib.Tc3_Module`; the unqualified rollup `TwinCAT.XAE.PLC.Lib` is not a valid substitute.
- Microsoft .NET Framework C# compiler, Windows SDK `TlbImp.exe`, and the VS2022 public `EnvDTE`/`EnvDTE80`/`Microsoft.VisualStudio.Interop` assemblies.
- Python 3.10+ and the root `multi-plc-agent` package, or the checkout root on `PYTHONPATH`. No extra Python package is required by this backend.

Nothing is installed automatically. Check local package ownership before installing dependencies. `--sdk`, `--public-assemblies`, `--compiler` and `--tlbimp` select already installed SDK components; defaults match the verified workstation. Missing components cause an actionable error, never a fabricated compiler success. Other versions/editions are unverified.

The original C# worker is compiled once per server process against those public components in a temporary directory. Generated interop/worker binaries are not committed or redistributed.

## Start through the router

The `twincat` entry in [`config.example.json`](../../config.example.json) uses vendor `beckhoff`, prefix `beckhoff_`, and the checkout root on `PYTHONPATH`. Enable only the backends you intend to use. The existing `delta_` WPLSoft tools are unchanged; DIADesigner SV3 remains a separate unverified target.

Standalone from the checkout root, in PowerShell:

```powershell
$env:PYTHONPATH = (Get-Location).Path
python -m backends.beckhoff.beckhoff_mcp --allow-write --workspace "D:\PLC-Examples\Beckhoff"
```

Without `--allow-write`, validation and reads are available but project creation/overwrite is denied. The default workspace is the current user's `.multi-plc-agent/beckhoff` directory. Tools accept a `.sln` path only inside a **project subdirectory** of the configured workspace; absolute paths outside it and traversal/symlink escapes are rejected.

## Tools

| Router tool | Operation |
| --- | --- |
| `beckhoff_list_targets` | Bounded target/scope discovery; does not launch XAE or claim hardware support |
| `beckhoff_validate` | Validate variables/rungs and return PLCopen LD plus expected semantics; no writes |
| `beckhoff_write_ladder` | Create a native solution, author LD, save/reopen, compile, export and compare |
| `beckhoff_build` | Reopen an owned solution in a fresh host and run the actual native compiler |
| `beckhoff_export_pou` | Independently read MAIN, declarations and task binding; optional `include_xml` |

Rung JSON uses named IEC variables, NO/NC contacts, parallel branches, OUT/SET/RST coils, TON/TOF/TP and CTU. The complete native conveyor exercises branches, NC contacts, OUT, TON and CTU. Other accepted instructions have portable validation/codec coverage, not a separate new native/runtime claim. Timer/counter instances are declared automatically. The shared codec is `multiplc.iec_ld`; CODESYS uses the same implementation, not a copied backend.

A write requires a fresh empty destination. Existing **backend-owned** project directories require `overwrite=true`; the whole prior directory is preserved in a sibling `<directory>.bak` before a fresh project is created. An existing backup or unowned directory is never overwritten. A failed native operation leaves its actual result/partial project and any backup visible; it is not silently retried or reported as successful.

The standard-template MAIN is removed through the public native tree API before importing its replacement. This avoids an observed native import-in-memory/save mismatch: an import call and a passing compiler alone did not guarantee persistence. Matching independent readback after reopen is mandatory. `errors`, `warnings`, `failed_projects`, platform and readback flags remain separate; an absent native count is **unknown**, not zero. Counts reflect the vendor standard-template compiler settings, not a safety/static-analysis certification.

Native jobs have a bounded deadline. Any deadline termination is restricted to the newly created owned process handle; no process-name kill or arbitrary COM/shell executor is exposed. Host exit and timeout results are reported. Treat the configured workspace and local filesystem as trusted operator-controlled storage, not an OS sandbox.

## Protocol and evidence

The actual stdio entrypoint and router were exercised with MCP revision **2025-06-18**, initialization, discovery, native write/export/build and clean host teardown. Stdout contains newline-delimited UTF-8 JSON-RPC only. Intended IDE clients use the existing router registration; this run does not independently certify every IDE/version.

The GIF is **two actual native step captures** of the generated LD and successful build output, not a continuous authoring video or runtime simulation. Every exported frame was visually reviewed. Raw desktop captures and machine-specific receipts stay local; public receipts omit personal paths and process identifiers.

Public interface references, consulted 2026-11-03:

- [Beckhoff host ProgID](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/21842697995.html)
- [Beckhoff PLCopen import/export](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/21841320715.html)
- [Beckhoff native templates](https://infosys.beckhoff.com/content/1033/tc3_automationinterface/717817483.html)
- [Pinned MCP stdio transport contract](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)
