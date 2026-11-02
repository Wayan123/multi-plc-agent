# Seven Omron examples: LD through multi-plc-agent

Original learning examples in English. The LD source is CX-Programmer mnemonic in JSON, not a program to be executed on this machine. The `mcp/` folders contain **CXT/CXP projects actually written through the Omron MCP backend**, read back identically, and then compiled by CX-Programmer 9.75.

| Example | Model | Material | Native compile |
| --- | --- | --- | --- |
| [01](01-cp1h-x40dt-d/) | CP1H-X40DT-D | Start/stop, permissive, horn before motor, anti-auto-restart | 0 errors / 0 warnings |
| [02](02-cp1h-xa40dt-d/) | CP1H-XA40DT-D | Same digital logic; separate XA CPU profile | 0 / 0 |
| [03](03-cp1h-xa-analog/) | CP1H-XA40DT-D | Four AI, two AO, validity and output permit | 0 / 0 |
| [04](04-analog-scaling/) | CP1H-XA40DT-D | AI raw 0–6000 → -1000–1000; AO command 0–1000 → raw 0–6000 | 0 / 0 |
| [05](05-cp1h-xy-md02/) | CP1H-X40DT-D **and** CP1H-XA40DT-D | Modbus RTU FC04 XY-MD02; two native projects | 0 / 0 each |
| [06](06-cp2e-n30dt-d-xy-md02/) | CP2E-N30DT-D | Modbus RTU XY-MD02, CP2E-specific buffers/bits | 0 / 0 |
| [07](07-cp1h-x40dt-d-traffic-light/) | CP1H-X40DT-D | Four-way intersection and dedicated pedestrian phase, learning example | 0 / 0 |

**Seven cases, eight programs**, because case 05 must test X and XA separately. CP2E-N30DT-D maps to editor device `CP2E-N`, CPU `N`; 30 is a product specification, not an editor CPU name. The compiler verifies the CPU family profile, not the order code of a physical PLC.

## Files in each example

- `README.md`: configuration, rung sequence, conceptual wiring, addresses, evidence limits, sources.
- `prompt.id.md`: complete reproduction specification/prompt for the case; **not a copy of the entire old conversation history**.
- `program.json` (case 05 has two model-named JSON files): LD mnemonics, explicit model/CPU, stimuli and expectations per scan.
- `program.il` / variant `.il` names: readable mnemonic listing derived from JSON.
- `signals.csv`: the sole address/type/unit/access-rights map for HMI consumers.
- `mcp/*.cxt`, `mcp/*.cxp`, `mcp/*.verification.json`: MCP-produced projects and actual compiler evidence. The source JSON is bound to that evidence by SHA-256.
- `verification.json`: per-case test summary; `manifest.json`: file inventory, hashes, variants, source references and native artifacts.

## Checks without hardware

From the repo root, with Python 3.10+ and no additional packages:

```bash
python3 contoh/omron/check.py
python3 contoh/omron/check_sync.py
python3 -m unittest discover -s tests -p test_omron_examples.py -v
```

`check.py` runs scenarios against the **limited mnemonic model** in `offline.py` and checks hashes and the binding of native evidence to source/CPU. It **does not run a new compiler**, CX-Simulator, a serial port, or a PLC. Native evidence is saved editor output; changing the source requires a new build/read-back/compile, not merely updating hashes.

The offline model rejects unsupported opcodes. Timers use a discrete 100 ms model; auxiliary inputs, analog data and gateway responses are supplied as stimuli. This tests logic and arithmetic, not physical scan timing, the Modbus driver, UART, PLC-calculated CRC, ADC/DAC, firmware or safety.

## Rebuilding through the installed MCP

Prepare Windows with a licensed CX-Programmer and the external Omron backend already installed. This repo does not include an unlicensed implementation of the external backend. Use your local router configuration; do not commit machine paths/credentials. The following command uses placeholder paths that **must be replaced**:

```powershell
python contoh/omron/mcp_build.py `
  --config C:\lokal\multi-plc-config.json `
  --program contoh/omron/01-cp1h-x40dt-d/program.json `
  --output C:\lokal\hasil-baru\CP1H_X.cxt `
  --draft-seed `
  --receipt C:\lokal\hasil-baru\mcp-receipt.json
```

Run it with a Windows interpreter that can run the router; the backend configuration must point to the correct Omron interpreter/server. The loader enables the Omron backend on a **new output** with write permission and editor auto-reload disabled. It rejects existing outputs, the wrong CPU, and template projects containing rungs. The option `--template C:\lokal\empty-X.cxt` can replace `--draft-seed` for a genuine empty export of the correct CPU.

Actual sequence: initialize router → discover backend → read empty project → add sections/rungs through Omron tools → validate → commit CXT/CXP → read back all instructions → check CPU. The loader does not treat MCP validation as a native compile.

After the build, open the new CXP in CX-Programmer, select the correct PLC and **PLC → Compile All PLC Programs**; record the model, version/check option and complete output. Going online or downloading is not required for this step. Compare read-back with the source; keep the receipt locally without exposing private paths. Regenerating the manifest and consumer pins is an explicit step after new evidence is approved, not an automatic fix when a check fails.

File/New initially failed because of the CX-Server working project. Testing succeeded using an original text seed with a CPU profile supported by installation metadata, then opened/compiled in the editor. No clock/installation changes were made and no CP1E template was disguised as CP1H/CP2E. The seed text-format version name is not evidence of the compiler version; compiler evidence is recorded separately.

## Synchronization with HMI-AI and Content Studio

This repository is the canonical source. HMI-AI stores **read-only logical signal references**, not copies of addresses/rungs. Content Studio stores example references and tutorial ideas; no weeks/statuses/calendar entries were shifted. Case 05 remains two variants; case 07 is a four-way intersection example for education, not certified traffic control.

For the local sibling layout used in development:

```bash
python3 contoh/omron/check_sync.py \
  --consumer ../../content-studio/plan/omron-example-refs.json \
  --consumer ../../HMI-AI/examples/omron/example-refs.json \
  --bindings ../../HMI-AI/examples/omron/bindings.json
```

Manifest pins, file changes, sources, models, signals and access permissions are checked. Requested siblings that are missing must cause failure; the checker does not silently download, clone or update pins. A public clone without siblings only needs the two canonical checks above. HMI-AI is not yet public; this work does not claim that a native HMI project or tutorial/video was created.

## Limits before commissioning

- **Not yet tested on a physical PLC or CX-Simulator.** Do not download to an operational machine. E-stop/guard/overload must use an appropriate hardware safety design.
- CP1H X has no built-in process analog I/O; XA has 4 AI/2 AO. PLC Setup, voltage/current switches, wiring and required restarts have not been applied to hardware.
- In 4–20 mA mode, raw 0 means 4 mA, not 0 mA. The program writes raw 0 when invalid; that **does not guarantee a 0 mA electrical output or fail-safe operation**.
- Modbus requires a suitable RS485 board and an actual sensor. The CP1H manual has an A640/A641 contradiction for port 1; the example selects the detailed D32200/A641 table and calls for hardware confirmation, rather than hiding the conflict.
- The gateway payload byte packing used is an **interpretation of the manual's table, not yet captured from a physical PLC**. Timeout, simultaneous error/normal, stale data and framing are tested as logic stimuli.
- XY-MD02 documentation comes from a distributor; the OEM manufacturer/clone variant has not been identified. Verify your unit's sensor manual/label, slave ID, baud/parity, registers, polarity and power supply.

Sources and fact locations: [SOURCES.md](SOURCES.md). All results must be read according to their level of evidence: file integrity ≠ offline model ≠ native compile ≠ field test.
