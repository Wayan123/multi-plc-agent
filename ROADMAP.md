# Roadmap

A status is recorded only after it has been run on real software. "Planned" means no backend code exists yet.

## GX Works3 (Mitsubishi iQ-F / iQ-R): blocked on the development machine

GX Works3 **1.055H** is installed on the development machine, but [Project] > [New] fails every time (6 of 6 tries, FX5U and R00): "Unable to execute the operation because memory is insufficient or system is unstable", then "R6025 – pure virtual function call". Install logs show an aborted GX Works3/GX Works2 uninstall shortly before the first crash; the faulting component is not confirmed. A repair or reinstall is needed before the write path below can be run. The existing `.gx3` files are FX3U compatible-mode projects and can't serve as an FX5U template. Window-message command IDs that open New (`0x9000`) and Open (`0x9001`) without the foreground are known. The research below comes from the GX Works3 Operating Manual SH-081215ENG-AQ and from read-only checks of the installed resource DLLs. The full notes are in [docs/gxworks3-research.md](docs/gxworks3-research.md).

| Path | Works on 1.055? | Evidence | Plan |
| --- | --- | --- | --- |
| Ladder editor **[Edit] → [Import File]** (listed-instruction CSV) + device comment CSV import | Yes. Added in 1.030G; labels/inline ST/FB in 1.040S, undefined FB/FUN in 1.055H | Manual §6.3 p.386–395, §6.8 p.499–500. Strings in `LadderEditor_RC2.dll` and `CommentEditor_RC2.dll` | **Primary.** This replaces GX Works2 "Read from CSV File" (manual Appendix 14, p.1221). gxworks-agent already writes the same 7-column UTF-16 CSV |
| Open I/F COM server `GXW3Call.dll` (`CreateNewProject`, `ImportProjectXml`, `BuildProject`, `SaveProject`) | Registered locally, `GetOpenIFVersion` = 13 | Type library read with pywin32. Not documented publicly | Later. The calling protocol and licence are unknown, and the managed wrapper is not installed |
| **Open Other Format File** on a `.gxw` produced by gxworks-agent | FX3U/UC/G/GC → FX5U/UC only | Manual §3.2 p.118–121, handbook JY997D66201 §5.4 | Fallback / cross-check. Parameters reset, needs admin rights |
| Writing `.gx3` files directly | No | OLE compound file with Jet DB streams, undocumented | Not planned |

### First milestone

The milestone is complete when the agent writes an FX5U MAIN program (start/stop self-hold plus a timer, with device comments) and the backend does the following:

1. Imports the program into a new GX Works3 1.055 project through [Edit] → [Import File].
2. Imports the comment CSV.
3. Runs Convert with **0 errors**.
4. Exports the program back to CSV, with no differences from the file it imported.
5. Saves the project as `.gx3`.

GX Works3 will be listed as supported only once that run passes.

### Questions to answer hands-on first

1. What header and module-type lines does 1.055 write when exporting an FX5U program?
2. Does it accept a GX Works2-style CSV?
3. Can pywinauto/UIA reach the Codejock command bars, or are keyboard accelerators needed?
4. What changes are needed to lower ladder to FX5: SM/SD devices instead of M8000/D8000, and the FX5 forms of timers and counters?

## Delta ISPSoft / DIADesigner, Schneider Machine Expert, Beckhoff TwinCAT: planned, not installed

| Target | Planned write path | First check |
| --- | --- | --- |
| Beckhoff TwinCAT 3 XAE (TC31-FULL) | TwinCAT Automation Interface (official COM/.NET) with PLCopen XML import and build. Large parts of the CODESYS backend (PLCopen LD generation, logic read-back) are expected to carry over | Only runtime parts of 3.1.4024.62 are installed; the XAE shell (`TcXaeShell.exe`) is missing |
| Delta ISPSoft 3.x (DVP-SE/SV2, AS) | Text/PLCopen import if available; otherwise file format like WPLSoft | Install and inspect Import/Export |
| Delta DIADesigner (AS/AX) | CODESYS-based: try the CODESYS backend with DIADesigner's profile | Is ScriptEngine exposed? |
| Schneider EcoStruxure Machine Expert (M241/M251/M262) | CODESYS-based ScriptEngine, same as `backends/codesys` | Profile name and device IDs |
| CODESYS 3.5 SP22+ | Compare with the official CODESYS MCP Server add-on (needs a Professional Developer Edition licence) | Optional |

The CODESYS-based tools reuse is an assumption until each is run.

## Other candidates (not installed)

Ranked by how often they appear in Indonesian and Asian machine building and by whether an official write path exists.

| Target | Note |
| --- | --- |
| Rockwell Connected Components Workbench (Micro800, free) | Check import/export of ladder |
| Rockwell Studio 5000 (ControlLogix/CompactLogix) | `.L5X` XML import/export is official; licence required |
| Inovance AutoShop (H3U/H5U) / InoProShop (AM/AC) | AutoShop: check IL import. InoProShop is CODESYS-based |
| LS Electric XG5000 (XGB/XGK) | Check IL text import/export |
| Keyence KV Studio (KV-8000/KV-X) | Check mnemonic text import |
| Xinje XDPPro, Panasonic FPWIN GR7 | Check IL/mnemonic import |
| Schneider Control Expert (M340/M580) | XEF/ZEF XML import/export; expensive licence |
| ABB Automation Builder, B&R Automation Studio | CODESYS-based (ABB); B&R: check text/ST import |

## Improvements to existing backends

| Target | Note |
| --- | --- |
| Omron CP1L / CP1H / CJ2 | The Cx-Proggrammer-MCP file format already works. Address ranges and the instruction set must be added. That backend has no published licence; an in-repo Omron CX-Programmer backend would remove the dependency |
| Siemens TIA Portal V21 | Supported by the backend (`runtime/v21`). Not yet run here |
| Sysmac Studio: XML export read-back, `.smc2` export, I/O mapping | XML export is licence-gated on the development machine; read-back currently parses the stored listing |
| Machine Expert - Basic: comparisons, word operations, CTD, more templates | Codec supports bit logic, TON/TOF/TP and CTU only |
| WPLSoft: rung (segment) comments, edge contacts, API instructions, ES2 template | Segment comment record not yet decoded |
| Haiwell: direct `.hwb` block import | File > Import > Program accepts a hand-edited block once its CRC-16/MODBUS section checksums are recomputed (checked on V2.2.13). A full encoder would replace keystroke entry and lift the branch limits |
| Haiwell: more CPU templates, TON 10 ms/100 ms base, nested branches | Keystroke entry supports TON with 1 s base only and one level of parallel branches |
| Demo recordings for CODESYS, Sysmac, Machine Expert - Basic and WPLSoft | Verified by tool output; recordings pending |
| Outseal Studio: upload | Deliberately not exposed: it writes to a board |
