# multi-plc-agent

One MCP server that lets an AI agent write ladder logic in several PLC engineering tools: Mitsubishi GX Works2, Siemens TIA Portal and Omron CX-Programmer.

multi-plc-agent does not drive any PLC software by itself. It starts one existing MCP server per tool, gives every tool a vendor prefix (`mitsubishi_`, `siemens_`, `omron_`) and exposes them as one server. Each backend keeps its own approval flow and safety checks. The router adds one shared rule on top: tools that act on a live PLC or delete project content are not exposed.

## Supported software

| Vendor | Software | Backend | How it writes | Verified on |
| --- | --- | --- | --- | --- |
| Mitsubishi | GX Works2 1.580 and 1.635 | [Wayan123/gxworks-agent](https://github.com/Wayan123/gxworks-agent) (fork of [Arienax/gxworks-agent](https://github.com/Arienax/gxworks-agent)) | Drives the GX Works2 UI: CSV import of the program and device comments | 1.580.0.1 English UI, FX3U: program and comments imported, Check Program "No error found" |
| Siemens | TIA Portal V20 / V21 | [bulaofen0036-coder/TIA_Portal_Openness_MCP](https://github.com/bulaofen0036-coder/TIA_Portal_Openness_MCP) v2.7.8 | Official TIA Openness API: LAD as S7DCL text, timers/counters as SCL external source | V20, S7-1200 1212C: FB + FC + OB1 + tags imported, compile 0 errors / 0 warnings |
| Omron | CX-Programmer 9.x, CP1E | [BlackUppsss/Cx-Proggrammer-MCP](https://github.com/BlackUppsss/Cx-Proggrammer-MCP) | Edits `.cxt`/`.cxp` project files directly | 9.75, CP1E-NA: project opened, compile 0 errors / 0 warnings |
| Mitsubishi | GX Works3 | none yet | Planned: ladder editor [Edit] → [Import File] CSV | Not supported. Write path researched, not yet run; see [ROADMAP.md](ROADMAP.md) |

"Verified on" lists only what was actually run. Other CPUs and versions may work, but they have not been tested.

## Demo

The same conveyor specification was written into each tool by the agent through this router: start/stop with E-stop, a 3 s warning horn before the motor starts, and a stop after a batch of 10. The demo then checks the result in the vendor software. The recordings are unedited apart from title cards. Waits are sped up and labelled on screen. Videos are attached to the [v0.1.0 release](https://github.com/Wayan123/multi-plc-agent/releases/tag/v0.1.0):

| Video | Shows |
| --- | --- |
| `multi-plc-agent-demo.mp4` (4 min) | All three in sequence |
| `demo-gxworks2.mp4` | GX Works2 1.580: import 5 rungs + 11 comments, Check Program "No error found" |
| `demo-cxprogrammer.mp4` | CX-Programmer 9.75: 6 rungs + 9 symbols written to the project file, Compile 0 errors / 0 warnings |
| `demo-tiaportal.mp4` | TIA Portal V20: 10 tags, SCL timing FB, LAD FC and OB1 calls, Compile 0 errors / 0 warnings |

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

## Safety

Generated ladder logic is a draft. Review it and test it in a simulator (GX Simulator2, PLCSIM, CX-Simulator) before it reaches equipment. Emergency stop, guarding, two-hand control and overload protection must be implemented by independent safety hardware, not by AI-generated logic.

## Development

```powershell
py -3 -m pip install pytest
py -3 -m pytest tests -q
```

The tests start fake stdio backends. They need no PLC software.

## License

Apache-2.0, see [LICENSE](LICENSE). Backends are separate projects under their own licenses, see [NOTICE](NOTICE). This repository does not include or redistribute their code.
