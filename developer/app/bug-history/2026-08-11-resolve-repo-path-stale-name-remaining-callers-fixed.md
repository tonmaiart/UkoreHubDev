# Remaining `resolve_repo_path`-from-name call sites fixed (completes 2026-07-20 entry)

## Symptom

Same latent bug as
[2026-07-20 — Playblast written into the wrong repo folder after a
rename](2026-07-20-repo-path-resolved-from-stale-name.md): for any repo
renamed after creation, Explorer's file browser, Repo Git Status
(Submit), the Local Repository "Remove Local Repositories" page, and the
repo-changed hook fired from `main_window.py` would all resolve to a
folder computed from the repo's *current* display name instead of its
real on-disk location — silently pointing at a nonexistent (or wrong)
folder.

## Root cause

That earlier entry's "Not yet fixed" list named these four call sites and
explicitly said to check whether they'd been resolved before assuming
they still needed auditing — they hadn't been:

- `interface/main_window.py`'s `_fire_repo_selected`
- `interface/repo_settings/local_repository_page.py`'s `_local_path`
- `plugins/core/explorer/repo_browser_page.py`'s `set_repo`
- `plugins/core/submit/repo_git_status_page.py`'s `_dest_path`

All four still called `resolve_repo_path(workspace_root, project.name,
repo.name)` instead of reading the already-stored `repo.local_path`. (The
fifth item on that list, `plugins/core/maya_launcher/plugin.py`, no
longer exists in the codebase — that plugin was removed/restructured
since 2026-07-20, so nothing to fix there.)

This surfaced while implementing an unrelated feature (deriving
`Repo.local_path`/`CatalogEntry.folder_name` from the git remote URL
instead of the display name, in `core/vcs/paths.py`'s new
`extract_git_repo_name` — see git history) — that change makes
`local_path` diverge from `sanitize_folder_name(repo.name)` immediately
for every *newly created* repo, not just renamed ones, which would have
made all four latent bugs above trigger far more often.

## Fix

All four now build the path as `Path(workspace_root) / repo.local_path`
directly, matching the pattern already used by
`PublishApi/repo_paths.py` and `project_editor/project_graph_view.py`
since the original fix. `core/vcs/paths.py`'s `resolve_repo_path` remains
correct for its one legitimate caller, `core/storage/metadata_store.py`'s
`add_repo` (repo-creation time, before `local_path` exists).

## Lesson

Same lesson as the original entry, reaffirmed: **grep for
`resolve_repo_path` before trusting that a "not yet fixed" list from an
older bug-history entry is stale.** A flagged-but-deferred systemic bug
doesn't fix itself, and an unrelated feature change can turn a rare
edge case (rename) into the common case (every new repo).
