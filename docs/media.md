# Demo videos

The full-length demo videos (MP4, 1080p) are kept outside GitHub so that the repository and its releases stay small. Short GIF previews live in [`docs/demo/`](demo) and the source-linked example directories.

**Video folder (Google Drive):** MEDIA_LINK: *link coming soon*

| File | Tool | Length |
| --- | --- | --- |
| `multi-plc-agent-demo.mp4` | GX Works2, CX-Programmer and TIA Portal in one run | 3 min |
| `demo-gxworks2.mp4` | Mitsubishi GX Works2 1.580, FX3U | |
| `demo-cxprogrammer.mp4` | Omron CX-Programmer 9.75, CP1E-NA | |
| `demo-tiaportal.mp4` | Siemens TIA Portal V20, S7-1200 1212C | |
| `demo-outseal.mp4` | Outseal Studio 3.6, Nano V5 | |
| `demo-haiwell.mp4` | Haiwell Happy 2.2.13, AT16S0T/P (typing phase at 3×) | |
| `demo-codesys.mp4` | CODESYS V3.5 SP21, Control Win V3 x64 (headless build at 4×) | 52 s |

The folder contains `SHA256SUMS.txt` with a checksum for each file.

The [Omron CPU instruction probes](../contoh/omron/cpu-probes/) include seven
`omron-cpu-*.gif` previews in `docs/demo/`. Each uses two actual native window
captures, before save and after reopen/recompile, cropped/resized and checked for
private content. These are labelled step captures, not continuous recordings,
runtime simulation or physical PLC evidence.

The [Beckhoff conveyor](../contoh/beckhoff/01-twincat-rt-x64-conveyor/) and
[Delta SS2 conveyor](../contoh/delta/01-dvp-ss2-conveyor/) each include a
`native-evidence.gif`: two actual owned native-window step captures, inspected
frame by frame. Beckhoff shows LD/native build; Delta shows saved LD and IL with
the native compile-complete message. Neither is continuous authoring, runtime
simulation or hardware evidence.

The [OIP conveyor pilot](../contoh/beckhoff/02-oip-conveyor/) includes one
[actual simulation GIF](../contoh/beckhoff/02-oip-conveyor/media/oip-internal-conveyor.gif),
also embedded in the root README without duplicating the binary. It is a
30.8-second, 960×540, 5 fps recording of the internal OIP IEC/Jolt simulation,
not a Beckhoff runtime recording. Its 1,495,016 bytes fit the existing preview
limit. The 1080p MP4 remains local and has not been uploaded to GitHub or Drive.

## Storage and billing scope

GIF previews are regular Git files, not Git LFS objects or Actions artifacts.
Keep each preview below the CI limit and reuse its path rather than committing
copies. Large recordings, render frames, dependency trees and runtime caches
must remain outside Git. Repeated binary revisions still grow Git history.

The repository's file-size check is a content policy, not an account-wide
spending cap. GitHub's [regular Git limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
are distinct from [Git LFS billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs)
and [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).
To prevent paid overages on metered products, review the owning account's
[budgets](https://docs.github.com/en/billing/how-tos/set-up-budgets), use a $0
budget with usage blocking where supported, and do not enable paid overages.
Adding a small regular-Git GIF does not verify or change those account settings.


## Rules for media

- Don't commit videos or other large binaries. CI rejects any tracked file over 2 MB and any `.mp4`, `.mov`, `.mkv`, `.avi` or `.webm` file.
- Don't attach videos to GitHub releases. Put them in the shared Drive folder and link them here.
- Before publishing a recording, minimize every other window, cover the desktop, and check the frames: no browser, billing pages, paths, user names or customer data.
- GIF previews: at most 2 MB each, 960 px wide, 8 fps or lower.
