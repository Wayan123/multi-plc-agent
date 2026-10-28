# Connecting AI clients

`multi-plc-agent` is a local stdio MCP server. Any client that can start a local MCP server can use it. The router can write the registration for you:

```powershell
multi-plc-agent --config C:\plc\config.json --client list                        # supported clients and their files
multi-plc-agent --config C:\plc\config.json --client codex                       # print the entry, change nothing
multi-plc-agent --config C:\plc\config.json --client codex --client-write        # merge it into the client's file
```

What `--client-write` does:

- It registers a server named `multi-plc` that starts the Python running the command (`python -m multiplc --config <absolute path>`). Run it from the Python environment you installed the router into.
- It merges this one entry into the file and keeps every other setting. If the file already exists, the previous version is saved next to it as `<file>.bak`.
- It refuses to touch a file that isn't valid JSON.
- Running it again with the same input changes nothing.
- Restart or reload the client afterwards.

## Clients

Formats come from each vendor's documentation, checked 2026-10-28. Some GUI backends need up to 15 minutes for one call, so the router sets a 900 s tool timeout wherever the client has a setting for it.

| `--client` | Client | File written (Windows) | Timeout set | Notes |
| --- | --- | --- | --- | --- |
| `vscode` | VS Code, GitHub Copilot agent mode | `<project>\.vscode\mcp.json` (`--project`, default current folder) | none documented | Uses the `servers` key. For the user profile, run **MCP: Open User Configuration** and paste the printed entry. |
| `copilot-cli` | GitHub Copilot CLI | `%USERPROFILE%\.copilot\mcp-config.json` | `timeout` 900000 ms | Default is 30 s. |
| `codex` | OpenAI Codex CLI, IDE extension, desktop app | `%USERPROFILE%\.codex\config.toml` | `tool_timeout_sec` 900 | Default is 60 s. The three Codex apps share this file. |
| `cursor` | Cursor IDE and Cursor CLI | `%USERPROFILE%\.cursor\mcp.json` | none available | The Cursor CLI ends tool calls after 60 s and this can't be changed. Use the IDE for GUI backends. |
| `devin` | Devin Desktop (Devin Local, Cascade), Devin CLI | `%APPDATA%\devin\mcp_config.json` | none documented | Devin cloud: see below. |
| `zcode` | Z.ai ZCode | `%USERPROFILE%\.zcode\cli\config.json` | none documented | Uses the `mcp.servers` key. |
| `claude-desktop` | Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | none documented | MSIX installs read `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`. Copy the printed entry there. |
| `claude-code` | Claude Code CLI, VS Code and JetBrains extensions | `%USERPROFILE%\.claude.json` (user scope) | `timeout` 900000 ms | Calls longer than 2 minutes continue as a background task. |
| `antigravity` | Google Antigravity (App, IDE, CLI) | `%USERPROFILE%\.gemini\config\mcp_config.json` | `timeoutSeconds` 900 | Default is 180 s per call. |
| `gemini-cli` | Gemini CLI | `%USERPROFILE%\.gemini\settings.json` | `timeout` 900000 ms | Default is 10 minutes. User-level servers are disabled in folders you haven't trusted; run `gemini` in a trusted folder. |

Any other client: print any `mcpServers` entry (for example `--client claude-desktop`) and adapt it. Most clients accept `command`, `args` and `env`.

The vendors' own commands do the same job, if you prefer them:

```powershell
claude mcp add-json -s user multi-plc '{"type":"stdio","command":"C:\\plc\\venv\\Scripts\\python.exe","args":["-m","multiplc","--config","C:\\plc\\config.json"],"timeout":900000}'
codex mcp add multi-plc -- C:\plc\venv\Scripts\python.exe -m multiplc --config C:\plc\config.json
gemini mcp add -s user --timeout 900000 multi-plc C:\plc\venv\Scripts\python.exe -- -m multiplc --config C:\plc\config.json
copilot mcp add multi-plc --timeout 900000 -- C:\plc\venv\Scripts\python.exe -m multiplc --config C:\plc\config.json
```

## Cloud agents (Devin cloud, other hosted agents)

Hosted agents run stdio servers inside their own cloud machine. The PLC software (GX Works2, TIA Portal, CX-Programmer and the rest) is on your Windows PC, so a cloud agent can't reach it. The router also has no network transport. A network port would let anyone who reaches it drive the engineering software on your PC, and the project has no authentication or TLS to protect such a port.

Use a client that runs on the same Windows PC as the PLC software. All clients in the table above do.

## WSL

The backends must run on Windows. A client running in WSL should therefore start the Windows Python: point `command` at the Windows interpreter (for example `/mnt/c/plc/venv/Scripts/python.exe`) and give the config as a Windows path (`C:\\plc\\config.json`). This setup is untested.

## Checked with real clients

On 2026-10-28, with isolated config folders, entries written by `--client-write` were read back by:

- `codex mcp list`: listed and enabled, with the working directory set.
- `claude mcp list`: connected; Claude Code started the router and completed the MCP handshake.
- `gemini mcp list`: listed, and disabled until the folder is trusted, as Gemini CLI documents.

The other clients were checked against their documentation only.
