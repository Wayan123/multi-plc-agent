# Roadmap

Status is recorded only from runs on real software. "Planned" means no code exists yet.

## GX Works3 (Mitsubishi iQ-F / iQ-R): planned

GX Works3 1.055 is installed on the development machine, but no backend exists. gxworks-agent targets only GX Works2. Open questions:

- **Write path.** Either drive the GX Works3 UI, as gxworks-agent does for GX Works2, or edit `.gx3` project files offline. The `.gx3` format is undocumented.
- **Program import.** GX Works3 offers no CSV program import comparable to GX Works2's "Read from CSV File". Device comments can be imported, but ladder probably has to be entered another way.
- **Version and locale.** The same version checks are needed that gxworks-agent uses for GX Works2 (menu command IDs taken from the resource DLLs).

GX Works3 will be listed as supported only after a ladder program written by the agent has been compiled in GX Works3.

## Other candidates

| Target | Note |
| --- | --- |
| Omron CP1L / CP1H / CJ2 | The Cx-Proggrammer-MCP file format already works. Address ranges and the instruction set must be added. |
| Omron Sysmac Studio (NJ/NX) | Different tool and project format. No backend known. |
| Siemens TIA Portal V21 | Supported by the backend (`runtime/v21`). Not yet run here. |
