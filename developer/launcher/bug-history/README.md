# bug-history/

A record of real bugs found and fixed in the launcher tooling — not a
changelog of features, only genuine defects (crashes, silent failures,
wrong behavior). Same convention as `../../app/`'s own
`developer/app/bug-history/` — started 2026-08-09 back when this was still
its own separate dev repo (`UkoreHubLauncherDev`), before that repo merged
into this one as `developer/launcher/`. Entries below predate the merge and
reference the old repo's paths/script names (`launcher_build/updater.py`,
`commit-main.ps1`, etc.) in their own bodies — read them for the mechanism
and Lesson, not as current path references; current equivalents are noted
in the index below where they've moved.

**Before changing code in an area that has an entry below, read that entry
first** — most entries end with a "Lesson" describing a pattern to avoid,
not just what happened once.

Never shipped to artists: `developer/` (this whole folder included) is
never checked out in the first place by `developer/release_launcher.ps1`'s
publish step (see `../README.md`) — nothing to strip, since only the
tracked `UkoreHubLauncher.exe` file is ever pulled from `main`.

## Index

- [2026-08-09 — `commit-release-fast.ps1`'s origin push got rejected with a diverged/unrelated history](2026-08-09-fast-commit-push-rejected-unrelated-histories.md) — now `developer/release_launcher.ps1` (see `../README.md`)
- [2026-08-09 — Self-update's `git clean -fd` wiped `launcher_config.json` and looped forever asking for the workspace path](2026-08-09-self-update-clean-wiped-workspace-config.md) — now `developer/launcher/launcher_build/updater.py` (`ensure_up_to_date`) (systemic — read this one before removing `.gitignore` from anywhere, or before changing `ensure_up_to_date`)

## Adding a new entry

One file per bug, named `YYYY-MM-DD-short-slug.md`, with these sections:

- **Symptom** — what was actually observed, in the reporter's words if useful.
- **Root cause** — the real mechanism, with file:line references. If it
  isn't fully confirmed, say so explicitly rather than guessing a
  definitive cause.
- **Fix** — what changed and where.
- **Lesson** — the reusable pattern to watch for next time, not just a
  restatement of the bug. This is the part that actually prevents
  recurrence — write it for someone who hasn't read the rest of the entry.

Add the new file to the Index above in the same commit.
