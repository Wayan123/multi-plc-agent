# GX Works3 write paths for an MCP backend (multi-plc-agent)

Development machine: GX Works3 **1.055H** (`GXW3.exe` FileVersion 1.055.0.1, uninstall entry "GX Works3 1.055H"), GX Works2 1.580E, Windows 11 via WSL2. All local findings below are read-only observations (string scans of DLL resources, type-library reads, OLE structure listing of a copied `.gx3`). No GX Works3 process was started; a process check after the COM probe showed none running.

## Sources

- **[OM]** GX Works3 Operating Manual SH(NA)-081215ENG-**AQ** (July 2025), the newest revision I could download as PDF: https://eu-assets.contentstack.com/v3/assets/blt5412ff9af9aef77f/blt30efb89167cad5ce/6878b462ca36bc8260270574/sh081215engaq.pdf . The Mitsubishi download page lists revision **AU** (2026/07): https://www.mitsubishielectric.com/fa/products/faspec/download.page?formNm=SW1DND-GXW3_SW1DND-GXW3-EC_6938&kisyu=%2Fplcl&lang=2&popup=1 . I did not obtain AU itself. Page numbers below are the printed AQ page numbers.
- **[NF]** GX Works3 new-function list (Japanese edition, release notes from Ver.1.0xx to 1.128J, 2026/07): https://dl.mitsubishielectric.co.jp/dl/fa/software/update/plc/0000000378/o_file/n_function.html
- **[HB]** Transition from MELSEC FX3G, FX3U, FX3UC Series to MELSEC iQ-F Series Handbook JY997D66201P: https://www.mitsubishielectric.com/dl/fa/document/manual/plcf/jy997d66201/jy997d66201p.pdf
- **[MX]** MX Component Version 5 Reference Manual SH-082395ENG-H: https://www.mitsubishielectric.com/dl/fa/document/manual/plc/sh082395eng/sh082395engh.pdf

## Main findings

1. **GX Works3 1.055 can import ladder from CSV.** The ROADMAP.md statement that GX Works3 "offers no CSV program import" is wrong. The ladder editor has **[Edit] → [Import File]**, which reads a listed-instruction CSV ("CSV (tab delimited)(*.csv)"). It was added in **1.030G** ([OM] Appendix 1, p.947ff). Labels, inline ST and FB/FUN calls in the CSV are supported from **1.040S**, and CSVs that use undefined FB/FUN from **1.055H** ([OM] p.387; [NF] 1.040S #11, 1.055H #19). Appendix 14 lists GX Works2 "Read from CSV File" as having the GX Works3 equivalent "Page 387 Importing from a CSV file" ([OM] p.1221). The manual also says GX Works2-made CSVs are rejected only when an MX-F project is open ([OM] p.387), which implies they are accepted for other CPUs.
2. **Device comments and labels can also be imported from CSV in 1.055** ([OM] p.499–500, p.329).
3. **1.055 ships a COM automation server, the "Open I/F" (`GXW3Call.dll`).** It is registered on this machine and reports Open I/F version 13. Its type library includes `CreateNewProject`, `OpenProject`, `ImportProjectXml`, `ExportObjectXml`, `BuildProject`, `RebuildProject` and `SaveProject`. The [OM] does not document it, I found no public Mitsubishi documentation, and the managed wrapper (`GXW3OpenIF32/64.dll`) that third-party tools use is not installed here.
4. **Converting .gxw → FX5U works on 1.055** for FX3U, FX3UC, FX3G and FX3GC sources ([OM] p.118; [HB] §5.4). FX3S sources need 1.080J. An FX5UJ target needs 1.065T.
5. **IEC61131-10 XML import (ST only) needs 1.110Q. Simulink XML import (ST) needs 1.100E.** Neither is in 1.055.
6. **MX Component only communicates with the PLC.** Its API covers device and buffer read/write, CPU status, clock and file reads, and no program write ([MX] function list).
7. **`.gx3` is an OLE compound file.** It contains nested OLE storage, Jet (Access) database streams and binary streams. No public writer exists.

---

## Ranked paths

### Rank 1. UI automation of the ladder editor's CSV import, plus device-comment CSV import (works on 1.055)

- **Feasibility on 1.055: yes.** Available since 1.030G, with labels/inline ST/FB from 1.040S and undefined FB/FUN from 1.055H.
- **Manual evidence:**
  - [OM] §6.3 "Importing/exporting ladder programs", p.386–395. The import procedure is: open the ladder editor, choose [Edit] → [Import File], select "CSV (tab delimited)(*.csv)", pick a "Conversion Method for Incorrect Instruction" (*Convert to 'OUT SM4095'* or *Convert to line statement*), then click [Yes].
  - File format, p.388. Tab- or comma-delimited. Fields containing delimiters are quoted. Columns from the 8th onward are ignored. The file must end with END. Statements, notes and P/I statements each have several accepted layouts.
  - Export format, p.390. UTF-16LE with BOM, tab-delimited, every field quoted, CRLF line ends.
  - Restrictions:
    - The import **deletes the existing program** in the target.
    - The imported program is left **unconverted**, so a Convert step is required afterwards.
    - Import is not possible while monitoring or simulating.
    - If the program file holds several programs, or the target is an FB/FUN, the program must be reassigned (Rebuild All) after import.
  - [OM] §6.8 "Exporting/importing device comments", p.499–500. Navigation → right-click the device comment → [Import File] or [Import Multiple Files]. Columns are matched by header name in any order, and **GX Works2-exported comment CSVs are accepted**.
  - [OM] "Exporting/importing a label", p.329. Label editor → [Edit] → [Import File] (CSV). GX Works2 CSVs are accepted after their headers are renamed.
- **Local evidence (strings, UTF-16):**
  - `WorkWindowPlugin/Ladder/en-US/LadderEditor_RC2.dll` contains:
    - dialog text: "CSV (tab delimited)(*.csv)|*.csv", "Convert to 'OUT SM4095'", "Convert to line statement", "Error found in the imported CSV file.", "Module Type Information:"
    - column headers: "I/O (Device)", "P/I Statement", "Step No.", "Note", "Instruction"
    - messages: "Failed to find the END instruction in the instruction list part of file to read.", "Export to File(&J)..."
    - file filter "All File Formats (*.csv;*.html;*.txt;*.xml)"
  - `en-US/Melco.GXW3.Resource.Common_RC2.dll` contains the menu items "Import &File", "&Export to File", "Export All Ladders".
  - `WorkWindowPlugin/Comment/en-US/CommentEditor_RC2.dll` contains "Import &File...", "Import Multiple &Files...", "&Export to File...".
  - `DialogPlugin/ImportExportDialog/en-US/Plugin_RC2.dll` contains "csv (tab delimited)(*.csv)".
  - `WorkWindowPlugin/Label/en-US/Plugin_RC2.dll` contains "Import &File...", "Export to &CSV File.", "Export to XML &File.".
  - `Service/Managed/Melco.GXW3.Controller.Offline.ImportExport.Managed.DeviceComment.dll` exists.
- **Automation difficulty: medium.** The steps are the same as gxworks-agent's GX Works2 "Read from CSV File" flow: open the editor, click the menu, drive the file dialog, answer the confirmation dialog, run Convert (F4) or Rebuild All, then read the Output window. The GX Works3 menus are Codejock ToolkitPro command bars (`ToolkitPro1531vc100U.dll`), so menu access will probably need keyboard accelerators or UIA rather than Win32 menus. coder007rahul/gxworks3-mcp-bridge shows that the Output grid exposes a UIA `GridPattern` for reading build errors.
- **Reuse:** gxworks-agent already writes this CSV layout. `src/gxworks2/csv_export.py::_write_program_csv` emits UTF-16 tab-separated QUOTE_ALL CRLF rows with 7 columns (step, line statement, instruction, I/O, blank, PI, note), which matches the manual's format. Two things change for GX Works3:
  - The header and module-type lines must match what GX Works3 expects. Header names may be language-dependent.
  - Device and instruction lowering must target FX5/iQ-R. Examples: SM/SD instead of M8000/D8000, FX5 timer and counter forms, and no FX3-only instructions.
- **Risks:**
  - The import replaces the whole target program, so the tool needs a confirmation gate and a backup before every import.
  - Invalid instructions are silently turned into `OUT SM4095` or line statements unless the tool reads the Output window afterwards.
  - Header-language mismatch can break the import.
  - UI timing and focus problems, and the GUI needs an unlocked desktop.
- **Verification loop:** run [Edit] → [Export to File] (CSV) after Convert, then diff the result against the generated CSV. Unconverted programs cannot be exported (p.390), so a successful export also proves the program converted.

### Rank 2. GX Works3 Open I/F COM server `GXW3Call.dll` (present in 1.055, undocumented)

- **Feasibility on 1.055: the server is present; usability is unproven.**
- **Local evidence:**
  - `HKCR\WOW6432Node\CLSID` maps 7 coclasses to `C:\Program Files (x86)\MELSOFT\GPPW3\GXW3Call.dll`: GXW3CallProject, Session, Product, View, Communication, Transmitter and CompReg. The type library is `GXW3CallLib` {B315BAD7-5F04-4D1B-9689-EA2F41BC5BF4}.
  - Loading the type library (pywin32) shows these methods:
    - `IGXW3CallProject`: `CreateNewProject(path,title,saveType,plcSeries,plcType,languageType,timeout,uiMode,callID,rc)`, `OpenProject`, `AttachProject`, `SaveProject`, `SaveAsProject`, `CloseProject`, `ImportProjectXml(callID,path,importFlags,importMode,reserved,errors,rc)`, `ExportProjectXml`, `ExportObjectXml`, `BuildProject`, `RebuildProject`, `GetPOUNames`, `GetLabels`, `ChangePlcType`, `IsProjectCompiled`, `ImportPrivateData`/`PastePrivateData`.
    - `IGXW3CallSession`: `Connect`, `ProjectOpen`, `CheckSupport`.
    - `IGXW3CallView`: `ShowPOUBody`.
    - `IGXW3CallProduct`: `GetPlcTypeList`, `GetOpenIFVersion`.
  - In 32-bit PowerShell I instantiated GXW3CallProduct and called `GetOpenIFVersion`, which returned **13**. No GX Works3 process started.
  - `Service/Native/Melco.GXW3.Controller.OpenIF.Native.Impl.dll` (1.055.0.1) exports `CreateOpenIFController`.
  - `Service/Managed/Melco.GXW3.Controller.Project.Managed.XmlImportExport.Impl.dll` references PLCopen TC6 (`http://www.plcopen.org/xml/tc6_0201`). It also references Mitsubishi addData namespaces, including `.../xml/bodyMLD`, `bodyNetworks` and `projectDeviceCommentLists`. It contains the identifiers `PrepareLadderImport`, `CommitLadderImport`, `LadderImportExportData` and `XmlImportMode` (Replace/Skip/RenameElement).
  - The resource DLL `...XmlImportExport.Impl_RC2.dll` contains "If a ladder program using FB is included in the XML file to be imported...". **[INFERENCE]** The XML importer handles ladder bodies and device comment lists.
  - `GXW3OpenIF32.dll`/`GXW3OpenIF64.dll` are **not** installed. A search under MELSOFT found only `MSF_OpenIF.dll` and the native implementation DLL.
- **Third-party evidence:**
  - CMsoft "Import for Melsec" (cmariusz/MelsecAI.VSExt) is "Built on the GX Works3 Open Interface (GXW3OpenIF)". It imports and exports POUs, global labels and SDTs as PLCopen XML, and runs Build/Rebuild. It requires `GXW3OpenIF32.dll`/`GXW3OpenIF64.dll`, "package *GX Works3 Open I/F*", which may be an optional component in the installer.
  - Bibin-VR/GXBridge-MCP claims PLCopen XML export/import "including graphical layout", plus project creation and build.
  - A Reddit thread (r/PLC "GX Works 3 Open I/F", blocked to my fetcher) is quoted in its search snippet as saying the Open I/F "is the published API to allow C# and other .net code control the GX Works software".
- **Automation difficulty:** low once the Open I/F works (headless-ish, deterministic, typed return codes). It is high to get working without documentation. Every call needs `Initialize(lpCommandSender)` and a 32-byte `lpbCallID`, and that protocol is not documented. Calling the raw COM layer means reverse-engineering the protocol; the alternative is obtaining Mitsubishi's Open I/F package and its documentation.
- **Risks:** no public documentation, unclear licence or redistribution terms (CMsoft warns not to redistribute the OpenIF DLLs), and the server is 32-bit in-proc. Whether 1.055's XML import accepts ladder bodies is unverified. The Open I/F methods may also require a running GX Works3, which `Session.Connect` suggests.
- **Value:** if it works, it replaces most UI automation: create project → import XML (ladder and comments) → build → save, with no menus.

### Rank 3. Pipeline via GX Works2: gxworks-agent writes .gxw, then GX Works3 runs "Open Other Format File" (works on 1.055 for FX3U/UC/G/GC → FX5U/FX5UC)

- **Manual evidence:**
  - [OM] §3.2 "Opening a GX Works2 format project", p.118–121.
    - Menu: [Project] → [Open Other Format File] → [GX Works2 Format] → [Open Project].
    - Supported sources: universal and high-speed universal QCPU → R120CPU; universal process CPU → R120PCPU; redundant CPU; LCPU (1.060N+); FXCPU FX3S/FX3U/FX3UC/FX3G/FX3GC → FX5S/FX5U/FX5UC/FX5UJ. FX3U/FX3UC cannot become FX5S. The new module type is chosen in "Select the New Module Type/Conversion Method".
    - Requires "the latest GX Works2" installed. The source project must compile in GX Works2, have no security or user management, and not be compressed (.gwz).
    - Ladder, ST, structured ladder/FBD and SFC programs are retained. SFC needs GX Works2 1.585K+ for FX5 targets, and this machine has 1.580E, so SFC would be lost. Device comments are retained, with M8000+ remapped to SM8000+ and D8000+ to SD8000+. Parameters return to defaults. Ladders with ≥1000 consecutive statement lines or an "incorrect ladder" are deleted.
  - Version gates from [OM] Appendix 1 and [HB]:
    - FX3U/UC structured ladder: 1.015R/1.020W.
    - FX3G/GC: 1.040S.
    - FX5UJ target: 1.065T (not in 1.055).
    - FX3S source: 1.080J (not in 1.055).
    - LCPU: 1.060N (not in 1.055).
  - [HB] §5.4 "Conversion of the Projects" (printed p.70–72): GX Works3 1.020W+ and GX Works2 1.519R+ are needed. The project must be converted in GX Works2 first, security removed, and **administrator rights are required**.
- **Local evidence:**
  - `en-US/GXW3_RC2.dll` contains "Do you want to read GX Works2 format project and change module type to FX5UCPU?", "This function utilize the one of GX Works2 internally." and "Please install the latest version of GX Works2...".
  - `DialogPlugin/ProjectOperationDlg/en-US/Plugin_RC2.dll` contains "Open GX Works2 Format Project", "GX Works2 Format Project(*.gxw)|*.gxw" and also "All Single File Format Projects(*.gx3; *.gxw)". **[INFERENCE]** The normal Open dialog may accept .gxw as well.
  - `Service/Native/Melco.GXW3.Controller.ExternalData.Native.GXW2.Impl.dll` and `EntityComponents/Melco.GXW3.Entity.*.GXW2*.dll` exist.
- **Automation difficulty: medium.** It needs menu navigation, a file dialog, the module-type/conversion dialog, a sample-comments question, an Output-window read and [Project] → [Save As]. It reuses the whole existing gxworks-agent pipeline unchanged up to the .gxw. **[INFERENCE]** Open I/F `OpenProject` might accept a .gxw path; this is untested.
- **Risks:**
  - FX targets only (plus Q→R), so it cannot produce native iQ-R or FX5-only programs.
  - The output is FX3-style code with automatic replacements, which needs manual review.
  - Parameters are lost, the step requires admin rights, and two GUI applications are involved.
  - The converted .gxw must compile in GX Works2.
- **Use:** a fallback or demo path. It also cross-checks Rank 1, because converted output can be exported to CSV as a GX Works3-native template.

### Rank 4. Generate ST instead of ladder and paste it into the ST editor (works on 1.055)

- **Evidence:** coder007rahul/gxworks3-mcp-bridge (MIT) writes ST through Ctrl+A → Delete → clipboard paste. It reads code back for a hash check and reads compile errors from the Output grid (UIA GridPattern). It notes that the ST editor exposes no usable UIA TextPattern or ValuePattern. File-based ST import (IEC61131-10 XML) arrives only in **1.110Q** ([OM] p.147; [NF] 1.110Q #18), and Simulink PLC Coder XML in **1.100E** ([OM] p.146).
- **Difficulty:** low to medium.
- **Limitation:** the result is not ladder. Inline ST inside a ladder CSV is possible from 1.040S ([OM] p.391).

### Rank 5. Keyboard entry in the ladder editor (works, fragile)

[OM] p.356 "Entering ladders" describes typing each instruction into the element entry dialog. Automating it means sending keystrokes such as `LD X0⏎`. It is slow, depends on layout, and offers nothing over Rank 1. It is only a last resort if CSV import fails for a specific construct.

### Not viable

- **Writing .gx3 files offline.** In the copied `Test1.gx3` (923,648 bytes), `file` reports "Composite Document File V2". Its top-level streams are `_hdb` (a nested OLE file with 46 numbered streams) and XML diffgrams (`projectlist.xml`, `projectdatalist.xml`, `history.xml`, `dataprotection.xml`, `checkout.xml`, `label.xml`). `securitylevel.xml` and `user.xml` are actually "Standard Jet DB" (Access) files. `projectdatalist.xml` names logical items `MAIN.Program.pou`, `MAIN.Labels.lh`, `COMMENT.qcd`, `Global1.gh`, `Param.wpa`, `MAIN.res`. The format is undocumented and includes data-protection and history records. Open-source projects only read it (purinzan/gx3-cli-mcp, agentthink/gx-trace). The corruption risk is high.
- **MX Component.** [MX] lists only Open/Close, Read/WriteDeviceBlock/Random, Get/SetDevice, Read/WriteBuffer, Get/SetClockData, GetCpuType, SetCpuStatus and file read. It has no program write.
- **IEC61131-10 / Simulink XML menu import.** Both require newer versions (1.110Q and 1.100E) and import ST only.
- **Ladder clipboard paste from mnemonic text.** No manual section describes pasting instruction-list text. The ladder editor's clipboard strings concern its own cell data, such as "Failed to paste data on clipboard." and "Number of columns does not match...". `Melco.GXW3.Utility.Managed.ClipboardFormat.dll` implies a private format.

## Third-party projects

| Project | License | Last push | What it does |
|---|---|---|---|
| https://github.com/coder007rahul/gxworks3-mcp-bridge | MIT | 2026-08-01 | C#/.NET 10 FlaUI MCP server. Reads and writes ST in an open POU via clipboard, runs Rebuild All, returns Output-grid errors. Preview→confirm safety token. No ladder. |
| https://github.com/Bibin-VR/GXBridge-MCP | Proprietary, source not public | 2026-10-05 | README claims 46 tools: project create/save, build, PLCopen XML import/export "including graphical layout", download/run, device monitoring. Probably Open I/F-based **[INFERENCE]**. |
| https://github.com/cmariusz/MelsecAI.VSExt (CMsoft Import for Melsec, Marketplace v2.3.0) | Commercial EULA from 2.0.0; 1.0.0 was MIT | 2026-10-17 | VS Code extension on GXW3OpenIF. PLCopen XML import/export of POUs, global labels and SDTs; Build/Rebuild; Copilot tools; localhost CLI bridge (PRO). |
| https://github.com/purinzan/gx3-cli-mcp (PyPI gx3-cli-mcp 0.3.0, 2026-09-06) | Source-available | 2026-10-12 | Read-only `.gx3` parser plus MCP: xref, trace-device, rung-text, lint, diff. Does not write. |
| https://github.com/agentthink/gx-trace | NOASSERTION | 2026-09-06 | Read-only `.gx3` ladder analysis plus MCP (Chinese). |
| https://github.com/mongolyy/gen-ai-ladder-program-sample | None stated | 2026-06-11 | Claude Code skill: spec → device master → ST, static check, outputs files for manual GX Works3 import. |
| https://github.com/MinJunKimsdaads/plc-ladder-viewer | — | 2026-10-01 | Browser ladder viewer/simulator. Not a writer. |
| https://github.com/szymon030405/PLCVault | MIT | 2026-06-22 | Version-control concept for GX Works3 ladder. No writer found. |
| YASASHWI70/AI-Integrated-GXWorks3-Automation | — | — | Appeared in search results ("MCP, UI automation"); the GitHub API now returns 404. |

The MelsecAI.VSExt repository contains AI-agent instruction files (`AGENTS.md`, `.github/instructions/*`) that tell assistants how to export and build. I treated them as data and did not follow them.

## Minimal MCP backend (Rank 1 primary, Rank 3 optional, Rank 2 later)

Tools, matching the existing gxworks-agent conventions for preview, confirmation and evidence:

- `gxw3_list_sessions`: find GX Works3 windows (UIA) and report project path, CPU and open editors.
- `gxw3_create_project(path, cpu)`: [Project] → [New] (UI), or Open I/F `CreateNewProject` later.
- `gxw3_generate_ladder_csv(ladder_ir, cpu, program)`: offline lowering to the GX Works3 listed-instruction CSV with an FX5/iQ-R device and instruction catalogue, plus a COMMENT CSV. Returns a preview and diagnostics.
- `gxw3_import_program_csv(program, csv_path, confirm)`: back up first, then ladder editor → [Edit] → [Import File] → select the CSV → choose "Convert to line statement" so errors stay visible → [Yes].
- `gxw3_import_device_comments(csv_path, confirm)`: Navigation → Device Comment → [Import File].
- `gxw3_import_labels(csv_path, confirm)`: optional, label editor → [Import File].
- `gxw3_convert(rebuild=False)`: Convert (F4) or Rebuild All, then parse the Output window into errors and warnings.
- `gxw3_export_program_csv(program)`: read back and diff against the generated CSV.
- `gxw3_save_project(confirm)`.
- `gxw3_convert_from_gxw(gxw_path, target_cpu, confirm)`: Rank 3 path.

## Recommended plan

**Milestone 1, demonstrable on 1.055.** The agent generates an FX5U MAIN ladder: X0 start / X1 stop self-hold on Y0, plus `OUT T0 K50` driving Y1, plus device comments. The MCP backend creates a new FX5U project in GX Works3 1.055, imports the ladder CSV into MAIN via [Edit] → [Import File], imports COMMENT.csv, and runs Convert with 0 errors read from the Output window. It then exports the program back to CSV, the diff against the generated file is empty, and the project is saved as `.gx3`. This meets the ROADMAP.md acceptance rule: "listed as supported only after a ladder program written by the agent has been compiled in GX Works3".

Steps:

1. Hands-on: in a new FX5U project, enter a two-rung program by hand and export it to CSV. This gives the exact header and module-type lines for 1.055 in English and in the display language. Export a device comment CSV the same way.
2. Add an FX5 target profile to the lowering: CSV header, SM/SD devices, FX5 instruction names and timer/counter forms. Reuse the `_write_program_csv` writer shape.
3. Write the pywinauto (UIA) driver for import, convert and export, using the gxworks-agent GX Works2 driver as the pattern.
4. In parallel, probe the Open I/F. Try obtaining the "GX Works3 Open I/F" package from Mitsubishi or the installer. If it works, move create/open/convert/save to it and test `ImportProjectXml` with an XML exported by `ExportObjectXml` from the hand-made ladder.
5. Optional: wire up `gxw3_convert_from_gxw` as a fallback for FX3-style programs.

## Unknowns that need hands-on tests

1. Does 1.055 accept a GX Works2-style CSV (Chinese headers, "PLC信息" line) in an FX5U project? If it does, does it convert FX3 devices? Or must the header match GX Works3's own export language?
2. Exact column and header text that 1.055 writes for FX5U, and whether the step-number column is ignored on import.
3. How the "Conversion Method for Incorrect Instruction" dialog and the import confirmation appear to UIA. Can pywinauto reach the Codejock command-bar menus, or are keyboard accelerators needed?
4. Behaviour when MAIN is part of a multi-program file, or when the target is an FB (both need reassign/Rebuild All per p.387).
5. Open I/F: the `Initialize(lpCommandSender)` and CallID protocol; whether `Session.Connect` needs a running GXW3.exe; how to obtain GXW3OpenIF and its documentation and licence; whether 1.055's `ImportProjectXml` accepts ladder (bodyMLD) and device comment lists; whether `OpenProject` accepts `.gxw`.
6. Whether "Open Other Format" for .gxw runs without administrator rights here ([HB] says admin rights are required), and whether GX Works2 1.580E counts as "latest" (it is below the 1.585K needed for FX5 SFC).
7. FX5-specific instruction coverage of the existing ladder IR, such as timers, counters, high-speed and 32-bit forms, against what GX Works3 1.055 converts without errors.
