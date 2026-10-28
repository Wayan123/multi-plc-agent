# Connecting AI clients

`multi-plc-agent` is a local stdio MCP server. Any client that can start a local MCP server can use it. The router can write the registration for you:

```powershell
multi-plc-agent --config C:\plc\config.json --client list                     # clients, installed or not, and their files
multi-plc-agent --config C:\plc\config.json --client codex                    # print the entry, change nothing
multi-plc-agent --config C:\plc\config.json --client codex --client-write     # merge it into the client's file
multi-plc-agent --config C:\plc\config.json --client all --client-write       # every client installed on this PC
multi-plc-agent --config C:\plc\config.json --client status                   # where multi-plc is registered
```

What `--client-write` does:

- It registers a server named `multi-plc` that starts the Python running the command (`python -m multiplc --config <absolute path>`). Run it from the Python environment you installed the router into.
- When the router runs from a source checkout instead of an installed package, the entry also points the client at the checkout: through `cwd` where the client supports it, otherwise through `PYTHONPATH`. Clients start servers from their own folder, so without this `-m multiplc` would not be found.
- It merges this one entry into the file and keeps every other setting. If the file already exists, the previous version is saved next to it as `<file>.bak`.
- It refuses to touch a file that isn't valid JSON.
- Running it again with the same input changes nothing.
- Restart or reload the client afterwards.

`--client all` writes to every client whose folder exists on this PC (see `--client list`). `--client status` lists each client's file, whether `multi-plc` is in it, and whether its command still exists. It exits with 1 when an entry points at a Python that was moved or deleted; run `--client-write` again to fix it.

## User or project scope

By default the entry goes into your own user configuration, so it is available in every folder. `--scope project --project <folder>` writes it into that folder's configuration instead. Use this when only one PLC project should see the server, or to try it without touching your user files:

```powershell
multi-plc-agent --config C:\plc\config.json --client cursor --scope project --project C:\work\line1 --client-write
```

A project file contains absolute paths of your PC. Don't commit it to a shared repository unless everyone uses the same paths. Claude Desktop has no project configuration.

## Clients

The IDE, CLI and desktop versions of one product read the same file, so one `--client` covers all of them. Formats come from each vendor's documentation (sources in `multiplc/client_sources.json`, last reviewed 2026-10-28). Some GUI backends need up to 15 minutes for one call, so the router sets a 900 s tool timeout wherever the client has a setting for it.

| `--client` | Covers | User file (Windows) | Project file | Timeout set | Notes |
| --- | --- | --- | --- | --- | --- |
| `vscode` | VS Code with GitHub Copilot agent mode | `%APPDATA%\Code\User\mcp.json` | `.vscode\mcp.json` | none documented | Uses the `servers` key. Reload the window after writing. |
| `copilot-cli` | GitHub Copilot CLI | `%USERPROFILE%\.copilot\mcp-config.json` | `.github\mcp.json` | `timeout` 900000 ms | Default is 30 s. |
| `codex` | Codex CLI, Codex IDE extension (VS Code, Cursor, JetBrains), Codex desktop app | `%USERPROFILE%\.codex\config.toml` | `.codex\config.toml` | `tool_timeout_sec` 900 | Default is 60 s. Project files are read only in trusted projects. |
| `cursor` | Cursor IDE, Cursor CLI (`cursor-agent`) | `%USERPROFILE%\.cursor\mcp.json` | `.cursor\mcp.json` | none available | The Cursor CLI ends tool calls after 60 s and this can't be changed. Use the IDE for GUI backends. |
| `devin` | Devin Desktop (Devin Local, Cascade), Devin CLI | `%APPDATA%\devin\mcp_config.json` | `.devin\mcp_config.json` | none documented | Devin cloud: see below. |
| `zcode` | Z.ai ZCode | `%USERPROFILE%\.zcode\cli\config.json` | `.zcode\config.json` | none documented | Uses the `mcp.servers` key. |
| `claude-desktop` | Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` | none | none documented | Microsoft Store installs are detected and get `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`. Quit Claude from the tray and restart. |
| `claude-code` | Claude Code CLI, VS Code and JetBrains extensions, Code tab of the Claude desktop app | `%USERPROFILE%\.claude.json` | `.mcp.json` | `timeout` 900000 ms | Calls longer than 2 minutes continue as a background task. A project `.mcp.json` asks for approval on first use. |
| `antigravity` | Google Antigravity app, IDE and CLI | `%USERPROFILE%\.gemini\config\mcp_config.json` | `.agents\mcp_config.json` | `timeoutSeconds` 900 | Default is 180 s per call. |
| `gemini-cli` | Gemini CLI | `%USERPROFILE%\.gemini\settings.json` | `.gemini\settings.json` | `timeout` 900000 ms | Default is 10 minutes. User-level servers stay disabled in folders you haven't trusted. Gemini CLI refuses a `PYTHONPATH` override, so the entry uses `cwd`. |

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

On 2026-10-28, with isolated config folders, entries written by `--client all --client-write` and `--scope project` were read back by:

- `codex mcp list`: listed and enabled, with the working directory set.
- `claude mcp list` and `claude mcp get` (user and project scope): connected. Claude Code started the router and completed the MCP handshake.
- `gemini mcp list` in a trusted folder: connected.

The other clients were checked against their documentation only. Reports from other client versions are welcome; open an issue with the client version and the output of `--client status`.

## Keeping this current

Client config formats change. To catch that:

- `.github/workflows/client-docs.yml` runs monthly (and on demand from the Actions tab). It fetches every page in `multiplc/client_sources.json` and checks that the strings our format depends on are still there. If a page is gone or a string disappeared, it opens or updates the issue **Client MCP documentation changed**.
- You can run the same check locally: `python scripts/check_client_docs.py`.
- A test makes sure every client in `multiplc/clients.py` has a source in `client_sources.json`, so a new client can't be added without one.

When the check fails, re-read the page, update `multiplc/clients.py` and this file, set `checked` in `client_sources.json` to the date, and add a CHANGELOG entry.

### Adding a client

1. Add a `Client(...)` entry to `CLIENTS` in `multiplc/clients.py`: its user file, project file, key layout (`servers`, `mcpServers`, `codex-toml` or `zcode`), timeout key and whether it documents `cwd`.
2. Add its documentation page and two or three marker strings to `multiplc/client_sources.json`.
3. Add a row to the table above and verify with the real client if you have it.
