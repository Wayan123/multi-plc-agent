# Releasing

## Versions

The version lives in one place: `__version__` in `multiplc/__init__.py`. The package metadata, `multi-plc-agent --version` and the MCP `serverInfo` all read it.

Versions follow [Semantic Versioning](https://semver.org/). Before 1.0 the rules are:

| Change | Bump |
| --- | --- |
| A tool, argument or config key is removed or renamed, a default changes what the router exposes, or the config file format changes incompatibly | minor (0.x → 0.x+1), with a **Changed** or **Removed** entry that says what to do |
| New backend, new tool, new option | minor |
| Bug fix, docs, a backend verified on another software version | patch |

After 1.0, removals and renames need a major version.

The in-repo backends under `backends/` keep their own `__version__`. Bump it when that backend's tools or behaviour change.

## Release steps

1. Move the entries under **Unreleased** in `CHANGELOG.md` to a new `## [x.y.z] - YYYY-MM-DD` section and add its compare link at the bottom.
2. Set `__version__` to the same `x.y.z`. The test suite fails if `CHANGELOG.md` has no section for the current version.
3. Run the tests on Windows (`python -m pytest tests backends -q`) and `multi-plc-agent --config config.json --check` with every backend you have installed. In the PR, list the backends that you checked against real vendor software.
4. Merge, then tag the merge commit and push the tag:

   ```powershell
   git tag -a vx.y.z -m "vx.y.z"
   git push origin vx.y.z
   ```

5. Create the GitHub release from the tag and paste the changelog section into it. Do not attach videos or vendor files to the release (see [docs/media.md](docs/media.md)).

## Supported versions

Only the latest release gets fixes. Security reports follow [SECURITY.md](SECURITY.md).

## Dependencies

The router has no runtime dependencies. Dependabot opens monthly PRs for the GitHub Actions used in CI. Vendor software versions that each backend was verified with are listed in the README; a new vendor version is a patch release with a **Verified** note.
