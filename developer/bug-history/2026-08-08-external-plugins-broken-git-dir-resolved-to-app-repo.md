# 2026-08-08 — External Plugins' "Stage Untracked & Push" nearly staged/pushed the whole UkoreHub app repo into a repo plugin's remote

## Symptom

Using the new `plugins/core/ExternalPlugins/` "Stage Untracked & Push"
button against `cache/plugins/AdvancedSkeleton` (an auto-detected, "not
catalogued" row) listed dozens of untracked files with paths like
`developer/bug-history/...` and `plugins/core/ExternalPlugins/...` — files
that actually belong to UkoreHub's own app repo, not to AdvancedSkeleton.
`git add` then failed with `pathspec '...' did not match any files`, which
is what surfaced the problem — had the pathspecs happened to resolve, the
button would have committed and pushed UkoreHub's own local, uncommitted
changes into AdvancedSkeleton's remote (`UkoreHubDev.git`) instead.

## Root cause

`cache/plugins/AdvancedSkeleton/.git` (and `DreamwallPicker/.git`) exist
as directories but are completely empty — no `HEAD`/`config`/`objects`,
apparently left over from an interrupted or never-finished clone. `git -C
cache/plugins/AdvancedSkeleton rev-parse --show-toplevel` resolves to
`C:/Tonmai/UkoreHub` (the app's own repo root), because git's normal
repo-discovery walks up parent directories when the `.git` it finds isn't
a valid repository, instead of failing outright. Every gate in
`external_plugins_page.py` used `GitService.is_cloned()` — which only
checks `(local_path / ".git").exists()` — so this broken folder was
treated as a perfectly normal, valid clone, and every git subprocess call
made with `cwd=cache/plugins/AdvancedSkeleton` silently operated on the
UkoreHub app repo instead.

## Fix

Added `GitService.is_repo_root()` (`core/git_service.py`) — checks
`is_cloned()` first, then confirms `git rev-parse --show-toplevel` for
that path actually equals the path itself, not some parent repo.
`external_plugins_page.py` now gates every real git operation (Pull,
Check for Updates, Stage Untracked & Push) on `is_repo_root()` via a new
`_require_valid_clone()` helper, not `is_cloned()`; a broken `.git`
surfaces as its own explicit status (`_BROKEN_GIT`, "Broken .git directory
— delete the folder and Clone again") instead of silently being treated
as a normal, working clone. `is_cloned()` itself was left unchanged (still
just the cheap existence check) — it's used elsewhere in the app
(`project_graph_view.py`'s per-node render, `Notification`'s repo-switch
poll, `submit`'s status page) as a fast, best-effort UI status signal
where a subprocess call per check would be real added cost for a
same-day-rare edge case; `is_repo_root()` is the deliberately slower,
opt-in check for a caller about to mutate a repo.

## Lesson

`(path / ".git").exists()` is not proof `path` is a real, independent git
repository — an interrupted clone, a bad extraction, or any other way a
`.git` directory ends up empty/corrupt will make git's own discovery walk
up to whatever real repository is further up the tree, and every
subsequent git command silently operates on *that* repo instead of
erroring. Any code that's about to run a *mutating* git command (stage,
commit, push, pull — not just display a status label) against a path
whose `.git` came from anything other than this app's own successful
`GitService.clone()` call in the same session should verify with
`is_repo_root()` (or equivalent — confirm `rev-parse --show-toplevel`
matches) first, not just check for a `.git` directory's existence.
