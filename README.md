# multi-plc-agent

One MCP server that lets an AI agent write ladder logic in several PLC engineering tools: Mitsubishi GX Works2, Siemens TIA Portal, Omron CX-Programmer, Outseal Studio and Haiwell Happy.

multi-plc-agent starts one MCP server per tool, gives every tool a vendor prefix (`mitsubishi_`, `siemens_`, `omron_`, `outseal_`, `haiwell_`) and exposes them as one server. Each backend keeps its own approval flow and safety checks. The router adds one shared rule on top: tools that act on a live PLC or delete project content are not exposed. The GX Works2, TIA Portal and CX-Programmer backends are existing third-party projects; the Outseal and Haiwell backends live in [`backends/`](backends).

## Supported software

| Vendor | Software | Backend | How it writes | Verified on |
| --- | --- | --- | --- | --- |
| Mitsubishi | GX Works2 1.580 and 1.635 | [Wayan123/gxworks-agent](https://github.com/Wayan123/gxworks-agent) (fork of [Arienax/gxworks-agent](https://github.com/Arienax/gxworks-agent)) | Drives the GX Works2 UI: CSV import of the program and device comments | 1.580.0.1 English UI, FX3U: program and comments imported, Check Program "No error found" |
| Siemens | TIA Portal V20 / V21 | [bulaofen0036-coder/TIA_Portal_Openness_MCP](https://github.com/bulaofen0036-coder/TIA_Portal_Openness_MCP) v2.7.8 | Official TIA Openness API: LAD as S7DCL text, timers/counters as SCL external source | V20, S7-1200 1212C: FB + FC + OB1 + tags imported, compile 0 errors / 0 warnings |
| Omron | CX-Programmer 9.x, CP1E | [BlackUppsss/Cx-Proggrammer-MCP](https://github.com/BlackUppsss/Cx-Proggrammer-MCP) | Edits `.cxt`/`.cxp` project files directly | 9.75, CP1E-NA: project opened, compile 0 errors / 0 warnings |
| Outseal | Outseal Studio 3.6 (Nano / Mega boards) | [`backends/outseal`](backends/outseal) | Writes the `.plc` project file directly, then runs Studio's Test through UI Automation | V.3.6 Beta5, Nano V5: 7 rungs written, Test 0 errors, hex generated; codec round-trips all 18 bundled examples |
| Haiwell | Haiwell Happy 2.2.13 (C/T/N/H series) | [`backends/haiwell`](backends/haiwell) | Types rungs into the LD editor with its keyboard shortcuts, then exports IL and compares it with the expected IL | V2.2.13.240603, AT16S0T/P: 7 rungs written, IL read-back identical, compile 0 errors / 0 warnings |
| Mitsubishi | GX Works3 | none yet | Planned: ladder editor [Edit] → [Import File] CSV | Not supported. Write path researched, not yet run; see [ROADMAP.md](ROADMAP.md) |

"Verified on" lists only what was actually run. Other CPUs and versions may work, but they have not been tested.

## Demo

The agent wrote the same conveyor specification into each tool through this router:

- start/stop with an E-stop
- a 3 s warning horn before the motor starts
- a stop after a batch of 10 products

Each recording is one continuous run: the agent's MCP calls appear in the log window, and the result is then checked in the vendor software. The GIFs play at 1.5× speed. Paths on the development machine are masked.

### Mitsubishi GX Works2 1.580 (FX3U)

The agent imports 5 rungs and 11 device comments into MAIN, and Check Program reports "No error found".

![GX Works2 demo](docs/demo/demo-gxworks2.gif)

### Omron CX-Programmer 9.75 (CP1E-NA)

The agent writes 6 rungs and 9 symbols directly to the `.cxt`/`.cxp` project, which is then opened in CX-Programmer. Compile reports 0 errors and 0 warnings. The desktop is blurred while the agent writes the file, because CX-Programmer is not open yet at that point.

![CX-Programmer demo](docs/demo/demo-cxprogrammer.gif)

### Siemens TIA Portal V20 (S7-1200 1212C)

The agent creates 10 tags, an SCL FB for the timer and counter, a LAD FC and OB1 calls, and compile reports 0 errors and 0 warnings. FC_Conveyor and OB1 are then opened in the editor.

![TIA Portal demo](docs/demo/demo-tiaportal.gif)

### Outseal Studio 3.6 (Outseal PLC Nano V5)

The agent validates 7 rungs for the Nano V5 I/O range, writes the `.plc` file (read back identical), and Outseal Studio's Test reports 0 errors and builds the hex file.

![Outseal Studio demo](docs/demo/demo-outseal.gif)

### Haiwell Happy 2.2.13 (AT16S0T/P)

The agent types 7 rungs with network and component comments into the LD editor, saves, and the IL exported by Haiwell Happy matches the expected IL line for line. Compile reports 0 errors and 0 warnings.

![Haiwell Happy demo](docs/demo/demo-haiwell.gif)

Full-length MP4 videos (1080p) are attached to the [releases](https://github.com/Wayan123/multi-plc-agent/releases): `multi-plc-agent-demo.mp4`, `demo-gxworks2.mp4`, `demo-cxprogrammer.mp4` and `demo-tiaportal.mp4` (v0.1.0), and `demo-outseal.mp4` and `demo-haiwell.mp4` (v0.2.0).

## Install (Windows)

Install each backend you need by following its own README, then:

```powershell
git clone https://github.com/Wayan123/multi-plc-agent.git
cd multi-plc-agent
py -3 -m pip install .
copy config.example.json config.json
```

The router has no dependencies outside the Python standard library (3.10+).

Edit `config.json`, or set the variables it refers to:

| Variable | Points to |
| --- | --- |
| `GXWORKS_AGENT_DIR` | gxworks-agent checkout with its `.venv-mcp` |
| `TIA_MCP_DIR` | extracted `TIA_MCP_Delivery_v*` folder |
| `CX_MCP_DIR` | Cx-Proggrammer-MCP checkout with its `.venv` |
| `CX_PROJECT` | the `.cxt` file the Omron backend edits |
| `MULTIPLC_DIR` | this checkout (for the Outseal and Haiwell backends) |
| `GUI_PYTHON` | Windows `python.exe` with `pywinauto` and `pywin32` (Outseal and Haiwell) |

Set `"enabled": false` on any backend you don't use. Check that every backend starts:

```powershell
multi-plc-agent --config config.json --check
```

The command exits with 0 only when every enabled backend reports `running`.

## Connect an MCP client

```json
{
  "mcpServers": {
    "multi-plc": {
      "command": "multi-plc-agent",
      "args": ["--config", "C:\\path\\to\\config.json"]
    }
  }
}
```

Ask the agent to call `list_plc_backends` first. It returns each backend's status, server identity, exposed tool count and the tools that were withheld.

## What is not exposed

| Backend | Withheld by default | Why |
| --- | --- | --- |
| Siemens | `DownloadToPlc`, `GoOnline`, `SetWatchTableModifyValue`, every `Delete*`, `ClearExports`, `EnsureOpennessUserGroup`, `Doctor` | Live PLC writes, deletions, and a group change that runs through UAC |
| Siemens | The same names called through `CallTool` | `CallTool` reaches tools that aren't listed, so the router checks the inner name |
| Omron | `delete_rung` | Deletion |

To expose a withheld tool on one backend, add `"allow": ["ToolName"]` to it. To withhold more tools, use `"deny"`.

## Per-backend notes

- **GX Works2.** Native compile and live ST/FBD sessions still require 1.635.0.1. On 1.580, only Ladder CSV import and export are enabled. Save the project in GX Works2 yourself, because the tool won't save an unnamed project. The 1.580 support is proposed upstream in [Arienax/gxworks-agent#11](https://github.com/Arienax/gxworks-agent/pull/11).
- **TIA Portal.** Add your Windows user to the `Siemens TIA Openness` group yourself and sign in again before the first start. Otherwise the server tries to do it through UAC and exits if that fails. TIA Portal asks for Openness access on every connect unless you choose "Yes to all".
- **CX-Programmer.** The backend edits one project file, set by `--project`. Close the project in CX-Programmer before the agent commits. If it was open, close it **without saving** and reopen it. The backend was written for CP1E. Its address and instruction checks do not cover CP1L, CP1H, CJ or CS.
- **Outseal Studio.** `outseal_write_project` writes the file without the GUI; `outseal_compile` opens it in Outseal Studio and clicks Test. Addresses are checked against the board's I/O count. The backend never uploads to a board.
- **Haiwell Happy.** There is no ladder import, so `haiwell_write_ladder` types into the editor. Don't use the keyboard or mouse while it runs (about 2 minutes for 7 rungs); it stops if another window takes focus. It replaces the first program block and keeps a `.bak` copy. Supported: NO/NC contacts, parallel branches (first leg one contact, no nesting), one output per rung: OUT, SET, RST, TON (1 s base), CTU. Only the AT16S0T/P template is bundled; for other CPUs create the project in Haiwell Happy and pass its path.

## Safety

Generated ladder logic is a draft. Review it and test it in a simulator (GX Simulator2, PLCSIM, CX-Simulator, Haiwell Happy's offline simulator) before it reaches equipment. Emergency stop, guarding, two-hand control and overload protection must be implemented by independent safety hardware, not by AI-generated logic.

## Development

```powershell
py -3 -m pip install pytest
py -3 -m pytest tests -q
py -3 -m pytest backends/outseal/tests backends/haiwell/tests -q
```

The router tests start fake stdio backends, and the backend tests check file formats, validation and the Haiwell keystroke plan. None of them need PLC software. Set `OUTSEAL_SAMPLES` to a folder of Outseal Studio `.plc` files to round-trip them too.

## License

Apache-2.0, see [LICENSE](LICENSE). The GX Works2, TIA Portal and CX-Programmer backends are separate projects under their own licenses, see [NOTICE](NOTICE); this repository does not include or redistribute their code. The Outseal and Haiwell backends in `backends/` are part of this repository and under its license; `backends/haiwell/haiwell_mcp/templates/AT16S0T.gpc` is an empty project saved by Haiwell Happy.
