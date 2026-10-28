# Changelog

All notable changes to this project. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/) as described in [RELEASING.md](RELEASING.md).

## [Unreleased]

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

[Unreleased]: https://github.com/Wayan123/multi-plc-agent/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/Wayan123/multi-plc-agent/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Wayan123/multi-plc-agent/releases/tag/v0.1.0
