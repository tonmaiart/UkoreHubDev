# Self-update's `git clean -fd` wiped launcher_config.json and looped forever asking for the workspace path

## Symptom

A customer's `UkoreHubLauncher.exe` showed:

```
UkoreHub launcher update failed:
git clean -fd failed: warning: failed to remove
UkoreHubLauncher.exe.old-28712: Invalid argument

You can continue with the current version — restart to retry.
```

with only an Exit button. Restarting re-asked for the Workspace folder
(the setup checklist's Step 3) every single time, forever — not just once.

## Root cause

`ensure_up_to_date` (`launcher_build/updater.py`) forces the working tree
to match upstream via `git fetch` + `git clean -fd` + `git reset --hard`.
Until this fix, `git clean -fd` ran with no excludes at all, relying
entirely on this repo's `.gitignore` to keep it away from per-machine
files — `.gitignore` lists `/launcher_config.json` (the saved Workspace
path) and `/UkoreHubLauncher.exe.old-*` (the running exe's own
`_relocate_self_exe` rename-aside target, created moments earlier in the
very same update, still open/locked by this process) as ignored, so an
ordinary checkout's `clean -fd` skipped both.

The release repo (`UkoreHubLauncher`, what every artist machine's
self-update actually pulls from) stopped shipping a `.gitignore` at all
after `developer/commit-main.ps1` added it to `$excludePaths` (per
CLAUDE.md's "release repo never carries dev-only files" — a reasonable
ask on its own, artists never need to see it) — but nobody accounted for
`.gitignore` also being load-bearing for `git clean -fd`'s safety here.
Without it, `clean -fd` treated `launcher_config.json` as fair game
(deleted, hence the repeated Workspace prompt) and tried to delete the
locked `.old-<pid>` exe too — which Windows refused ("Invalid argument"),
making the whole `git clean -fd` command exit non-zero. Since `clean -fd`
ran *before* `git reset --hard`, that failure aborted the update before
`reset --hard` ever ran — so the exe binary on disk (which `reset --hard`
would have overwritten with a fixed build, once one existed) never
actually got updated either. The machine was stuck: every launch re-asked
for the Workspace path, then failed the exact same way trying to fetch
the fix that would have stopped it from asking.

## Fix

`ensure_up_to_date` no longer runs a bare `git clean -fd`. A new
`_clean_untracked` passes explicit `git clean -fd -e <pattern>` excludes —
one per line of this repo's own `.gitignore` — so the clean behaves
identically whether or not an actual `.gitignore` file is present in the
checkout it's running against. `_clean_untracked` also swallows a `git
clean` failure instead of propagating it (best-effort), so a single stray
file it still can't remove — locked by antivirus, a lingering handle,
whatever — can never again block the `reset --hard` right after it, which
is the step that actually delivers a fix.

## Lesson

A `.gitignore` file can be doing real protective work for tooling code
(here: keeping an unattended self-updater's `git clean -fd` away from
per-machine state and in-flight renamed files), not just keeping `git
status`/`git add -A` tidy. Before removing `.gitignore` from a repo (or
any path a `.gitignore` covers) — especially one a script reads or relies
on programmatically — check whether anything besides "what does `git add
-A` pick up" depends on those exact ignore patterns still applying.
Self-updater logic in particular should hardcode the paths it must never
touch rather than trusting an on-disk file it doesn't control the
lifecycle of. Separately: an unattended step like `git clean` that isn't
the actual point of the operation (the real goal here is `reset --hard`
delivering a fresh binary) should never be allowed to block the step that
is — make cleanup best-effort when the operation can safely proceed
without it.
