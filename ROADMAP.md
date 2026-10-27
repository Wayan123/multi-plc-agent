# Roadmap

A status is recorded only after it has been run on real software. "Planned" means no backend code exists yet.

## GX Works3 (Mitsubishi iQ-F / iQ-R): planned, write path identified

GX Works3 **1.055** is installed on the development machine. No backend exists yet. The research below comes from the GX Works3 Operating Manual SH-081215ENG-AQ and from read-only checks of the installed resource DLLs. None of it has been run hands-on. The full notes are in [docs/gxworks3-research.md](docs/gxworks3-research.md).

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

## Other candidates

| Target | Note |
| --- | --- |
| Omron CP1L / CP1H / CJ2 | The Cx-Proggrammer-MCP file format already works. Address ranges and the instruction set must be added |
| Omron Sysmac Studio (NJ/NX) | Different tool and project format. No backend known |
| Siemens TIA Portal V21 | Supported by the backend (`runtime/v21`). Not yet run here |
