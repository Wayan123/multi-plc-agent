# Omron example sources and evidence levels

Manuals are referenced, not copied into the repository. The code, ladder, signal tables and example explanations are original work. Page numbers below are printed pages; other editions may differ. `latest` URLs can change: match the edition/title, not just the URL.

| Source ID | Document | Facts used |
| --- | --- | --- |
| `omron-w450` | [W450 CP1H CPU Unit Operation Manual, E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1) | I/O §4-2-2 p153/§4-3 p159; built-in AD/DA §5-5 pp326–337; Serial Gateway §5-6 pp346–347; auxiliary Appendix G pp761–762 |
| `omron-w451` | [W451 CP1 CPU Unit Programming Manual, E1-03](https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1) | Signed/unsigned comparison instructions §3-6-1 pp211–214; MOV §3-7-1 p247; CPU programming/operation |
| `omron-w474` | [W474 CS/CJ/NSJ Instructions Reference](https://files.omron.eu/downloads/latest/manual/en/w474_cs_cj_nsj-series_plc,_sysmac_one_nsj_series_reference_manual_en.pdf?v=1) | Semantics of MOVL(498), *(420), /L(431), -L(411), ANDW(034), ORW(035), SWAP(637); SWAP uses a word count and an in-place operand |
| `omron-w614` | [W614 CP2E Software User's Manual](https://assets.omron.eu/downloads/latest/manual/en/w614_cp2e_software_users_manual_en.pdf) | Modbus-RTU Easy Master: port 1 D1200/A640, port 2 D1300/A641; command/response format and status |
| `omron-w613` | [W613 CP2E Hardware User's Manual](https://assets.omron.eu/downloads/latest/manual/en/w613_cp2e_hardware_users_manual_en.pdf) | CP2E-N models, I/O, serial option board, RS485 wiring; not a built-in serial port on units without a board |
| `omron-w483` | [W483 CP1E/CP2E Instructions Reference](https://assets.omron.eu/downloads/latest/manual/en/w483_cp1e_cp2e_cpu_unit_instructions_reference_manual_en.pdf) | CP2E instruction availability, word logic and SWAP(637) |
| `xy-md02-distributor` | [XY-MD02 manual — SAH distributor](https://www.sah.rs/media/sah/techdocs/xy-md02-manual.pdf) | FC04 input registers wire 0001/0002, signed temperature ×0.1°C/RH ×0.1%, default 9600 8N1/slave 1, 5–30 VDC supply; OEM identity and clone consistency are unconfirmed |

## Decisions that are not vendor facts

- The 3-second horn, start arming and anti-restart are teaching designs, not certified safety circuits.
- Allowing AO only when all four AI are valid is a conservative example policy, not an Omron requirement.
- The engineering range -1000..1000 and command 0..1000 are tutorial choices. Signed 32-bit integer arithmetic, rounding toward zero, clamping and word allocation are explained in case 04.
- 1-second polling, last-good retention, clearing `data_valid` at the start of a poll, error priority and buffer ownership are application designs.
- The response byte placement `0401 3102 22xx` is derived from the gateway response format; it has not been measured on a PLC. The last padding byte is ignored.
- **CP1H source conflict:** the detailed W450 table on pp346–347 maps port 1 to D32200/A641 and port 2 to D32300/A640, but the summary diagram/other supporting sources may show A640 for port 1. The examples use the detailed table and require actual port 1 testing before deployment. CP2E differs: port 1 D1200/A640.

## Local native evidence

On 2026-10-31 seven projects were written through the multi-plc-agent MCP router/Omron backend, instructions were read back identically, and **CX-Programmer 9.75 (9.7.5.6)** displayed 0 errors/0 warnings for all projects. Complete output is stored in `mcp/*.verification.json`; CP1H uses check option Unit Ver1.3, CP2E Unit Ver1.0.

Text seed CPUs were determined from installed Omron metadata `CX-Server/StaticData/.../CP1H/X`, `CP1H/XA`, and `CP2E-N/N`, then compiler acceptance was demonstrated. No vendor XML, external backend implementation, or private credentials/paths are included. The native compiler does not prove wiring, analog settings, gateway byte packing or physical sensor communication. No download, serial I/O or CX-Simulator was used in this testing.
