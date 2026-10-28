# Contributing

*Bahasa Indonesia: [CONTRIBUTING.id.md](CONTRIBUTING.id.md)*


Thanks for helping. multi-plc-agent is useful only if it is correct on real engineering software, so every claim of support must come from a run you actually did.

## What helps most

| Contribution | What to include |
| --- | --- |
| New backend for a PLC tool | See [Adding a backend](#adding-a-backend) |
| Verification on another version, CPU or UI language | Tool version, CPU, UI language, the exact tool calls, and the compile/build output |
| Bug report | Steps, expected vs. actual result, backend and tool version. Strip customer data |
| Docs and translations | English is the default (`README.md`, this file). Translations live next to it as `*.id.md` and may lag behind; English wins when they differ |

Open an issue before large work so we can agree on the write path first.

## Ground rules

1. **Only your own work.** Submit code, text and files that you wrote or that are under a license compatible with Apache-2.0, and say where third-party code came from.
2. **No vendor material.** Do not commit vendor manuals, help files, DLLs, installers, sample projects, licence keys or screenshots of licensed content. Short facts are fine: menu names, file-format field names, numeric command IDs, error texts needed to parse results.
3. **Templates.** A project template may only be an empty project that you saved yourself with the vendor tool. State the tool version in the PR.
4. **No customer data.** Test projects must be synthetic.
5. **No reverse engineering that a licence forbids.** If the vendor's terms prohibit decompiling or bypassing a protection, don't. Prefer official APIs (Openness, ScriptEngine, PLCopen XML import, CSV/text import) and public file formats.
6. **No live-PLC writes.** Backends must not download, go online, force I/O or write to a running controller. The router withholds such tools; backends should not expose them.
7. **Safety.** Generated ladder is a draft. Do not describe a backend as suitable for safety functions.

## Developer Certificate of Origin (DCO)

Every commit must be signed off:

```
git commit -s -m "codesys: support TOF"
```

This adds `Signed-off-by: Your Name <you@example.com>` and certifies the [Developer Certificate of Origin 1.1](https://developercertificate.org/): you wrote the change or have the right to submit it under the project's licence. Contributions are accepted under Apache-2.0 (inbound = outbound). You keep your copyright.

## Adding a backend

A backend is a stdio MCP server under `backends/<vendor>/<vendor>_mcp/`. Copy the shape of `backends/outseal` (writes a file) or `backends/codesys` (drives an official scripting API):

- Tools without the vendor prefix; the router adds `<vendor>_`. Minimum: `validate`, a write tool, a compile/build tool that returns error counts, and a read-back used to verify the write.
- Same rung JSON shape as the other backends (`{"comment", "elements": [contacts | {"branch": [...]}, ..., output]}`).
- Writing requires `--allow-write`. Never overwrite a file without an explicit flag; keep a `.bak`.
- Tests in `backends/<vendor>/tests/` that run without the vendor software and check behaviour (validation boundaries, codec round-trip, read-back comparison). Don't test wiring or copy strings.
- Proof in the PR: the conveyor demo spec (start/stop with seal-in, E-stop, 3 s start delay with horn, counter of 10 with reset, batch lamp) written, compiled with 0 errors in the real tool, and read back matching. Paste the outputs.
- Add the backend to `multiplc/config.py` (`VENDOR_DEFAULTS`), `config.example.json`, the support table in `README.md` (and `README.id.md` if you can) and `ROADMAP.md`. List the tool only under "Verified on" for what you actually ran. In the **Status** checklist of both READMEs, move the tool from **Planned** to **Supported** and check its box (`- [x]`) only after that run; a planned tool that isn't listed yet goes under **Planned** unchecked (`- [ ]`).

## Checks before a PR

```
py -3 -m pytest tests backends -q
```

Add only tests that would catch a real bug. One topic per PR. Add a line under **Unreleased** in [CHANGELOG.md](CHANGELOG.md) for any change a user would notice.

Reviews and merges are done by the people in [MAINTAINERS.md](MAINTAINERS.md). Releases follow [RELEASING.md](RELEASING.md).

## Conduct and security

Be respectful; see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). Report security problems privately as described in [SECURITY.md](SECURITY.md), not in a public issue.
