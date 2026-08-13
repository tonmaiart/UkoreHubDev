---
name: ukorehub-launcher
description: Recurring pitfalls in UkoreHub's launcher/self-update tooling (C:\Tonmai\UkoreHubDev\developer\launcher\) — commit-release-fast/release scripts, and updater.py's ensure_up_to_date self-update flow (git clean, pull-conflict cutovers, locked-exe replacement). Use this whenever reading, writing, or debugging developer/launcher/launcher_build/updater.py, developer/release_launcher.ps1, or any script that publishes/self-updates UkoreHubLauncher.exe or app/ — even if the user doesn't say "launcher" explicitly (e.g. "the self-update is stuck", "release script failed to push", "the exe won't update itself").
---

# UkoreHub launcher — self-update & release pitfalls

See `developer/launcher/README.md` for the folder's file-by-file layout and
`ukorehub-core`'s scoped-editing convention — this skill is only the
recurring gotchas in this area's self-update/publish logic, distilled from
real incidents.

## Unattended publish scripts must force-push, never suggest manual reconcile

A "fast"/no-review publish script (`developer/release_launcher.ps1` and its
predecessor) is the sole legitimate writer to its release branch. If the
remote push is ever rejected as diverged/unrelated histories, the failure
path must force-push, not print a message telling the operator to `git pull`
and reconcile by hand — nobody may be watching, and a merge between
genuinely unrelated histories never resolves itself. The specific process
that produced an unrelated (not just diverged) history against this repo's
origin was never conclusively identified — treat a future recurrence as the
same class of problem, not a new one.

## `git clean -fd` in a self-updater must never trust `.gitignore`'s lifecycle

`updater.py`'s `ensure_up_to_date` runs a `git clean -fd` as part of
bringing the launcher's own checkout up to date. A `.gitignore` file removed
from the release repo (even unintentionally) silently exposes per-machine
state (`launcher_config.json`, in-flight renamed files) to that clean —
`.gitignore` was doing real protective work, not just tidying `git status`.
Self-updater logic should hardcode the specific paths it must never touch
rather than trust a file whose lifecycle it doesn't control, and treat the
clean step itself as best-effort (never let it block the `git reset --hard`
that actually delivers the update).

## Replacing the running exe: rename aside, never delete-then-write

A file that is both git-tracked and the currently-executing binary makes
`git checkout`/`pull` fail to unlink it on Windows on every ordinary update
that changes its bytes (OS file-locking, not a git bug) — not just a
fresh-install edge case. The fix is to rename the running exe aside first
(Windows allows renaming a locked file even though it disallows
deleting/overwriting it), restore it on failure, and sweep leftover renamed
copies on the next launch. Since `UkoreHub.exe` moved to its own separate
release repo, this exact failure is now rare in practice (ordinary app-code
releases don't touch `UkoreHubLauncher.exe` at all) — but the rename-aside
handling is still needed for the launcher exe self-updating its own
slower-changing repo, so don't remove it as dead code.

## The one pull that crosses "still tracked → no longer tracked" needs its own handling

Moving a file the running app writes directly (e.g. a shared JSON store)
off git — the standard fix for the git-pull-conflict class of bug above —
creates a new, different hazard: the single pull that transitions that file
from tracked to untracked hits the identical "would be overwritten by
merge" conflict, and unlike an ordinary merge conflict it never
self-resolves, since the app keeps re-dirtying the file on every launch
before the next pull attempt. A fix that stops git-tracking an
actively-written file must explicitly handle that one crossing pull —
`git rm --cached --ignore-unmatch <path>` then retry the pull once — not
just verify that pulls are clean going forward.
