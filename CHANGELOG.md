# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) as described in [RELEASING.md](RELEASING.md).

## [Unreleased]

### Added
- Add 23 capability-adapted teaching examples across Siemens, Outseal, Haiwell, Delta WPLSoft, Schneider M221, CODESYS and Beckhoff: cases 01/02/07 on each backend, plus Siemens four-channel analog input/two-output and DINT scaling cases. Includes native source/readback, sanitized actual compiler receipts, read-only signal contracts, SHA-256 pins and an English availability matrix with unsupported combinations unchecked. Adds deterministic digital scan-model tests; these are not vendor simulations or physical-PLC tests.
- Original Beckhoff TwinCAT stdio backend (`beckhoff_`) using the public Automation Interface, with guarded workspace/overwrite, native compiler diagnostics and independent LD/declaration/task readback. The six-rung TwinCAT RT x64 conveyor passed router write, save/reopen, fresh-host export and rebuild with 0 errors / 0 warnings. Includes native source, sanitized receipts and a reviewed two-step GIF; CX7000, simulation and hardware remain unverified.
- Reproducible Delta DVP-SS2/WPLSoft conveyor example through the existing MCP backend: seven rungs, native project/save/reopen/recompile, identical saved IL and aliases, zero grammar errors, source pins and reviewed native LD/IL step GIF. This is not DVP28SV3/DIADesigner support; the driver exposes no separate warning count.
- Seven original [Omron CPU instruction probes](contoh/omron/cpu-probes/) for CP1H X/XA, CP2E N, CP1L M/L/L10 and CJ2M-CPU31, with explicit variant profiles, ready native CXP projects, decoded CXT references, exact compiler output and privacy-reviewed native step GIFs. Each passed CX-Programmer 9.75 compile (0 errors/0 warnings), save/reopen/recompile and fresh saved-CXP MCP instruction read-back. No simulator/hardware result is claimed; the locally corrected external implementation is not bundled.
- Revised the educational CP1H traffic light to use separate outputs for all 12 vehicle lamps and two pedestrian lamps, while retaining paired opposite-direction phases; rebuilt through MCP and compiled in CX-Programmer.
- Educational CP1H-X40DT-D four-approach traffic light with a dedicated pedestrian phase, startup/all-red clearance, original LD and offline scenarios. MCP read-back matches; CX-Programmer9.75 compile 0 errors/0 warnings. Not tested on hardware or CX-Simulator; not a certified traffic controller.
- Six original [Omron teaching cases](contoh/omron/): CP1H X/XA digital I/O, XA built-in analog, signed analog scaling, XY-MD02 Modbus for both CP1H models, and CP2E-N30DT-D Modbus. Includes full case prompts, signal contracts, seven CXT/CXP projects created through the installed Omron MCP backend, identical instruction read-back, and CX-Programmer9.75 compile evidence (all 0 errors/0 warnings). No physical PLC or CX-Simulator test is claimed.
- Standalone limited-mnemonic scenario runner, source/evidence hashes, guarded MCP rebuild command and fail-closed checks for optional local Content Studio/HMI-AI references. HMI bindings are read-only logical references, not a native HMI project; six tutorials remain unscheduled backlog.
- Sponsor button (`.github/FUNDING.yml`: Ko-fi plus the maintainer's links) and a **Support the project** section in both READMEs.

### Changed
- List every available teaching example and each Omron CPU instruction probe directly under README's Ready-to-use examples, grouped by vendor with individual links, targets and topics.
- Verify TwinCAT RT x64 offline engineering with the installed XAE/PLC SDK and three explicitly approved standard-library packages. DIADesigner SV3 project/device/POU/task creation and native export are observed, but its LD write/readback seam and CX7000 hardware configuration remain unverified.
- Share the proven CODESYS/TwinCAT PLCopen LD codec in `multiplc.iec_ld`; source-only CODESYS launches now use the root package or checkout `PYTHONPATH`.
- Check DCO against the pull request head rather than GitHub's synthetic merge commit.
- README (English and Indonesian): update the support checklist from actual native acceptance. Human-prose status consistency is reviewed alongside evidence rather than tested through exact README wording.

### Fixed
- The original Omron MCP example client's tool selector no longer collides with a tool payload's `name` field. Binary timer/counter probe seeds now explicitly select the native Binary resource mode and use the initial-seed `TIMX`/`CNTX` spelling; templates with a mismatched mode are rejected before writing. Native failure/correction evidence and local CPU validation findings are documented in [the CPU validation record](docs/operations/omron-cpu-validation.md); external backend changes are not bundled.
- Correct the Omron workflow documentation: simulator/physical PLC tests are separate evidence levels, not prerequisites for commits, GIFs or publication. Runner-specific GUI preconditions are not project-wide release gates; real compiler diagnostics remain necessary for new native-verified support claims.

## [0.5.0] - 2026-10-28

### Added
- `--client all` registers the router in every AI client installed on this PC; `--client list` shows which are installed.
- `--scope project --project <folder>` writes the entry into a project's own config (`.vscode/mcp.json`, `.cursor/mcp.json`, `.mcp.json`, `.codex/config.toml`, `.devin/mcp_config.json`, `.zcode/config.json`, `.agents/mcp_config.json`, `.gemini/settings.json`, `.github/mcp.json`).
- `--client status` reports where `multi-plc` is registered and exits with 1 when an entry points at a Python that no longer exists.
- Monthly workflow `client-docs` checks the vendors' MCP config pages (`multiplc/client_sources.json`) and opens an issue when one changes.

### Changed
- `--client vscode` now writes the VS Code user profile (`%APPDATA%\Code\User\mcp.json`) by default; the workspace file needs `--scope project`.
- Claude Desktop installed from the Microsoft Store is detected and gets its packaged config file.

### Fixed
- Entries written from a source checkout failed to start (`No module named multiplc`) because clients launch servers from their own folder. The entry now sets `cwd` or, where the client has no `cwd`, `PYTHONPATH` to the checkout.

## [0.4.0] - 2026-10-28

### Added
- `--client <name>` prints the MCP registration for VS Code, GitHub Copilot CLI, OpenAI Codex, Cursor, Devin, ZCode, Claude Desktop, Claude Code, Google Antigravity and Gemini CLI. `--client-write` merges it into the client's file, keeps the other settings and saves a `.bak`. A 15-minute tool timeout is set where the client supports one. See [docs/clients.md](docs/clients.md).
- Backend contract test: every in-repo backend starts over stdio, answers `initialize` and `tools/list` with valid schemas, offers no online, download or upload tools, and refuses writes without `--allow-write`.
- CI on Windows as well as Linux, a 2 MB file-size and no-video guard, and Dependabot for GitHub Actions. The DCO check skips Dependabot's PRs.
- Indonesian translations in `*.id.md`; the English files are the default.

### Changed
- Demo videos moved out of the repository and the GitHub releases; see [docs/media.md](docs/media.md).
- The package version is read from `multiplc.__version__`, so the `--version` output, the MCP `serverInfo` and the package metadata agree. Earlier releases reported `0.1.0` at runtime.

### Fixed
- CODESYS and Machine Expert - Basic readers no longer test an XML element's truth value. Python is changing that behaviour (DeprecationWarning in 3.12+), which would have misread an empty element.

## [0.3.0] - 2026-10-28

### Added
- CODESYS V3.5, Sysmac Studio 1.47, Machine Expert - Basic 1.3 and WPLSoft 2.52 backends, each verified through the router with read-back.
- CONTRIBUTING (DCO sign-off), CODE_OF_CONDUCT, SECURITY, issue and PR templates, CI tests with a DCO check, NOTICE.

### Fixed
- In-repo backends write UTF-8 to stdout; the Windows code page broke non-ASCII replies.

## [0.2.0] - 2026-10-28

### Added
- Outseal Studio 3.6 and Haiwell Happy 2.2.13 backends.

## [0.1.0] - 2026-10-27

### Added
- Router that exposes GX Works2, TIA Portal and CX-Programmer MCP servers as one server, withholds online/download tools by default, and reports backend status through `list_plc_backends`.

[Unreleased]: https://github.com/Wayan123/multi-plc-agent/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Wayan123/multi-plc-agent/releases/tag/v0.1.0
