# Self-update kept failing on "local changes would be overwritten by merge" even after data/projects.json moved off git

## Symptom

After [2026-08-09-shared-data-git-pull-conflict.md](2026-08-09-shared-data-git-pull-conflict.md)'s
fix landed (removing `data/projects.json`/`programs.json`/`system_config.json`/
`data/plugins/core/*.json` from git tracking, moving them onto Google Cloud
Storage instead), machines that already had one of these files sitting on
an older, pre-migration commit still hit the exact same
`git pull failed: ... local changes to the following files would be
overwritten by merge` error on every self-update attempt — indefinitely,
not just once.

## Root cause

The earlier fix's own "Fix" section reasoned: "Once these files are no
longer git-tracked, the self-update `git pull` simply never touches them
again — the conflict can't recur structurally." That's true **after** a
machine successfully lands on the migration commit — but says nothing
about the one pull that actually crosses that commit boundary.

Right up until that pull, the file is still tracked at the machine's own
`HEAD`, and the running app keeps writing straight to it every launch
(`MetadataStore.save()` etc., no commit step — same root cause as the
earlier entry). So from git's point of view the file is always "locally
modified" relative to `HEAD`. The incoming migration commit *deletes* that
same file from tracking — and `git pull` (`developer/packaging/updater.py:225-229`'s
`ensure_up_to_date`, and the identical near-duplicate `core/self_update.py:45`'s
`pull_update`) refuses to apply a deletion over a locally-modified tracked
file, for exactly the same reason the original bug happened. Since the app
re-touches the file on every single launch, this isn't a one-time
annoyance that resolves itself — the affected machine is stuck retrying
the identical failing pull forever, unable to ever reach the commit that
would fix it.

## Fix

Both `ensure_up_to_date` and `pull_update` now catch a `git pull` failure
specifically containing `"would be overwritten by merge"`, and retry
exactly once after a new helper (`_untrack_paths_deleted_upstream`, defined
identically in both files per their documented near-duplicate
relationship) runs `git rm --cached --ignore-unmatch -r <path>` for every
path `git diff --name-only --diff-filter=D <local_head> <upstream_head>`
reports as deleted by the incoming commits. `git rm --cached` only removes
a path from git's index — the actual file on disk (and the data in it) is
untouched — so once the blocking paths are untracked locally, the retried
`git pull` applies the same deletion cleanly instead of refusing it. Any
other pull failure (or a repeat of the same one after the retry) still
raises normally.

## Lesson

Moving a file that the running app writes directly (no commit step) off
git — the fix for the *previous* entry's bug — creates a **new**,
separate transition hazard: the one pull that crosses from "still tracked"
to "no longer tracked" hits the identical conflict the migration was
meant to prevent, on every machine that hasn't crossed it yet, and (unlike
an ordinary merge conflict) never resolves on its own since the app keeps
re-dirtying the file every launch. A fix that removes a file from tracking
in a repo an auto-updater `git pull`s needs to also handle *this specific*
pull gracefully (untrack-then-retry, as above) — not just verify that
future pulls are clean. Check for this whenever a future change stops
git-tracking a file that's still actively written to locally.
