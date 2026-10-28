# Maintainers

| Name | GitHub | Area |
| --- | --- | --- |
| Wayan Dadang | [@Wayan123](https://github.com/Wayan123) | Router, all in-repo backends, releases |

## How decisions are made

- The maintainers review and merge PRs. A PR needs one maintainer approval and passing CI.
- A maintainer may merge their own PR after CI passes when no other maintainer exists. Changes to safety defaults (what the router withholds, `--allow-write` gates) still wait 48 hours on an open PR so others can comment.
- Disagreements are settled in the PR or issue. If that fails, the maintainers decide by majority; with one maintainer, the maintainer decides and writes down why.

## Becoming a maintainer

A contributor who has landed several reviewed PRs, for example a backend verified against real vendor software, can be invited by the existing maintainers. Each new maintainer is added to this file in a PR.

## Owning a backend

A contributor who adds a backend can be listed here as that backend's owner. Owners are asked to review PRs that touch their backend and to re-verify it when the vendor software changes. A backend that fails against the current vendor version and has no owner for 6 months may be marked unmaintained in the README.

## Stepping down

Maintainers who step down move to an **Emeritus** list in this file. Access is removed after 12 months without activity, after asking first.
