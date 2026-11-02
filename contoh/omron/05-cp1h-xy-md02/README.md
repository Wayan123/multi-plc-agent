# CP1H-X40DT-D and CP1H-XA40DT-D: read XY-MD02 via Modbus RTU

An **offline** educational example; not a commissioning program tested on a sensor. It never writes sensor configuration (FC06/FC10), connects to a serial device, or downloads to a PLC. The LD sources are `cp1h-x40dt-d.json` and `cp1h-xa40dt-d.json`, with input/expect scenarios executed against the same instructions. `program.il`/`.il` files show mnemonics for reading; CXT/CXP files in `mcp/` were generated through the MCP router. Per-file compile status is in `verification.json`; it is not a field-test claim.

## Equipment and settings that must match

- PLC **CP1H-X40DT-D and CP1H-XA40DT-D**; use **slot1/serial port1** in this example. Both X and XA require an RS485 option board; the USB port is not RS485.
- CP1W-CIF11 or CP1W-CIF12; choose the board according to the isolation/distance required, not just connector similarity.
- Port PLC Setup: **Custom, 9600 baud, 8 data bits, 1 stop bit, no parity (8N1), Serial Gateway**. Timeout0 = **5 seconds**, not no timeout. Apply PLC Setup according to the manual/power cycle, only during authorized commissioning.
- CP1W-CIF11 two-wire: DIP2 ON, 3 ON, 4 OFF, 5 ON, 6 ON; DIP1 ON only if the board is at the end of the bus. Do not copy another converter's DIP settings. CPU CP1H SW4 OFF so slot1 uses PLC Setup (SW5 for slot2).
- Sensor according to the SAH/HESTORE-distributed XY-MD02 manual: supply **5–30VDC**, ID1, 9600 8N1. OEM identity cannot be established and units with the same label may differ. Do not automatically try FC03/address0 as a fallback.
- Connect according to **polarity**, not A/B letters alone: Omron SDB+ to the sensor terminal marked +; SDA− to the − terminal. Photos of an XY-MD02 variant show A+/B−, but check your unit's labels. FG is not a sensor power terminal. Do not connect or power devices from the example script.

## Master block used

| Function | Address |
|---|---|
| Slave ID | D32200 = #0001 |
| Function | D32201 = #0004 (FC04) |
| Request byte count (excluding ID/function/CRC) | D32202 = #0004 |
| Starting address **on the wire** | D32203 = #0001 |
| Register count | D32204 = #0002 |
| Request and busy; automatically OFF after completion | A641.00 |
| Normal / error completion | A641.01 / A641.02 |
| Raw Omron error | D32252 |
| Response data count | D32253 |
| Raw response payload | D32254..D32256 |

**CP1H manual conflict:** the detailed W450 tables on pages 346–347 and the Auxiliary table use A641 for port1/D32200; the summary diagram on page 345 and the Omron KB article use A640. This example chooses the detailed tables rather than hiding the difference. Verify the mapping on the unit during commissioning before polling.

Address 0001 in the sensor manual is already the on-wire address. **Do not subtract 1 again**. Complete request: `01 04 00 01 00 02 20 0B`; the PLC calculates CRC, which is not included in the command data.

## LD, scan order and validity

1. Startup resets application results/status; it never RSETs `A641.00`.
2. Enable `W10.00` for polling. A 1-second timer separates transactions; only one transaction at a time; wait for system busy OFF before filling the command block.
3. The completion branch is evaluated **before** the launch branch. Only transactions owned by the application may be accepted. An old normal flag on the launch scan does not count as a new success.
4. Error takes precedence over normal. Success requires ID1, FC04, error0, data count5 and byte-count prefix04. `format_error=1` indicates an application response/completion validation error, including a malformed response or completion with neither normal nor error flag. It is separate from the raw Omron error in D102.
5. The manual's example response `01 04 04 01 31 02 22 2A CE` = **30.5°C / 54.6%RH**. Easy Master packing assumption derived from the manual/gateway: three words `0401 3102 22xx`; padding byte `xx` is unused. **This packing has not been observed on a physical PLC.** Do not `MOV` two raw words as the result.
6. Mask/swap scratch values only, using `ANDW(034)`, `SWAP(637) &1`, `ORW(035)`. Temperature is stored as signed16 x10, humidity as unsigned16 x10. `FF33` =−205 →−20.5°C. There is no BCD/float conversion.
7. `data_valid` is OFF on launch/error/disable. The last value may remain visible **only as stale**, not for control. Success publishes both values on the same scan; the HMI must read validity, not treat zero as success. Each status bit has one writer.
8. The timer is also reset on the completion scan; a transaction that completes between two scans does not cause a new poll immediately on the same scan.
9. Disabling polling while a transaction is still busy **does not cancel** the transaction or reset the system bit. A valid completion may update the last-good values while disabled, but `data_valid` remains OFF. After re-enabling, wait for a new successful transaction before using the values for a valid display.

## Repeatable tests

From the repo root: `python3 contoh/omron/check.py`. Scenarios check normal operation, negative temperature, nonzero padding, timeout, simultaneous normal+error, slave exception, wrong ID, wrong byte count, disable and busy at startup. Scenarios supply auxiliary flags/payload; the evaluator is **not CX-Simulator** and does not prove CRC/timing/physical polarity.

To rebuild through MCP: follow `../README.md` and use one of the JSON files in this folder. `mcp_build.py` rejects a different CPU, refuses to overwrite output, and saves a local receipt. The original text seed option uses an editor-proven CPU profile; it does not use a CP1E template. Draft files do not save PLC Setup serial settings—set them manually with the correct range before authorized commissioning.

## Sources

- [Omron W450-E1-08](https://files.omron.eu/downloads/latest/manual/en/w450_cp1h_cpu_unit_operation_manual_en.pdf?v=1), §6-1-3 pp.344–347; §6-1-4 p.349; DIP pp.45–50.
- [Omron W614-E1-03](https://assets.omron.eu/downloads/latest/manual/en/w614_cp2e_software_users_manual_en.pdf), §14-4 pp.14-14–14-26; timeout settings pp.7-7/7-11.
- [Omron W613-E1-03](https://assets.omron.eu/downloads/latest/manual/en/w613_cp2e_hardware_users_manual_en.pdf), board pp.3-18–3-23, wiring A-48.
- [XY-MD02 manual (distributor SAH; OEM not identified)](https://www.sah.rs/media/sah/techdocs/xy-md02-manual.pdf), pp.1,3–6.
- [Omron W451](https://files.omron.eu/downloads/latest/manual/en/w451_cp1_cpu_unit_programming_manual_en.pdf?v=1), ANDW436,ORW439,SWAP586–587; [W483 CP1E/CP2E](https://assets.omron.eu/downloads/latest/manual/en/w483_cp1e_cp2e_cpu_unit_instructions_reference_manual_en.pdf), ANDW2-225,ORW2-227,SWAP2-268.

Shared source/risk list: `../SOURCES.md`. Do not change the program, manual, HMI pins or tutorial separately without running the synchronization checks.
