# plugins/core/submit/

Moved here (2026-08-13) from `app/plugins/core/submit/README.md`. See
`plugins-guide.md` for the general plugin-authoring conventions this
plugin follows.

The Submit tab (`SectionRegistry` key `repo_git_status`) — stage/unstage/
revert, commit → pull → (resolve conflicts) → push. A real always-on
`plugins/core/` plugin — not special-cased by `interface/`, registers into
`SectionRegistry` the same way any other plugin would.

- `manifest.json` — plugin id `submit`, entry point `plugin.py`.
- `plugin.py` — `register(api)`: constructs `RepoGitStatusPage` from
  `api.metadata`/`api.local_config`/`api.git`, registers it as the
  `SectionSpec(key="repo_git_status", order=20, ...)` section. Also wires
  `background_threads` (reaches into every `QThread` worker attribute the
  page owns — `_git_worker`/`_status_worker`/`_stream_worker`/
  `_stage_worker`/`_unstage_worker`/`_revert_worker`/`_diagnostics_worker`/
  `_commit_log_worker` — for `MainWindow.closeEvent`'s shutdown cleanup) and
  `wire` — connects `sync_started`/`sync_finished`/`sync_failed` to
  `UICommandService.set_status_message` (the sidebar status line),
  `browse_file_requested` to `UICommandService.navigate_and_focus` (jumps to
  Explorer's `"repo_browser"` section key and calls its optional
  `browse_to_path` protocol method — see
  `plugins/core/explorer/repo_browser_page.py`), and `sync_finished` to
  `UICommandService.refresh_section("repo_browser")` (tells Explorer to
  rescan its current folder, without switching to its tab — see "Explorer
  refresh after Sync" below). See
  `plugin_api/registries/section_registry.py`'s `UICommandService` for why
  this is a fixed set of named callbacks rather than a generic dispatcher.
- `submit_section.ui` — Qt Designer file for the whole page, loaded at
  runtime by `RepoGitStatusPage` via `PySide6.QtUiTools.QUiLoader` (see
  "Loading the .ui file" below). Edit this in Designer to change layout/
  labels/spacing — no Python change or rebuild needed, just restart the app.
- `repo_git_status_page.py` — `RepoGitStatusPage`: the top-level Submit
  page. Drives the full sync/commit/pull/push workflow via the workers
  below, and shows the Modified/Staged/diagnostics/commit-history tables.
  `start_sync()` (the clone/pull behind "Sync New Commit") only ever
  runs from the Sync button click — there is no automatic clone/pull on
  launch or repo switch anymore (removed 2026-08-22, along with
  `interface/main_window.py`'s old `_start_auto_sync`/`AutoSyncPage`
  protocol, so opening the app or switching repos in Project Editor can
  never itself trigger a merge conflict — the user now controls sync
  timing entirely via this button). `set_repo()` (the `SetRepoPage`
  protocol method, still called on launch/repo-switch) only reads current
  on-disk status via `refresh_status()`, it never syncs. Before the
  very first clone of a repo (`start_sync` sees
  `git_service.is_cloned(dest_path)` is False) and only when the remote is
  a github.com URL, `start_sync` runs `core/vcs/repo_access.py`'s
  `check_repo_access` in a `GitStreamWorker` first
  (`_begin_access_check`/`_on_access_checked`) — if the current GitHub
  account can't see the repo, an "Access Denied" dialog fires immediately
  and the clone is never attempted, instead of letting git itself fail with
  an opaque error. A repo that's already cloned, or whose remote isn't
  github.com, skips straight to `_begin_sync_worker` as before.
- `commit_dialog.py` — `CommitDialog`: commit message entry (+ amend
  checkbox), shown before the pull→push workflow starts. Untouched by the
  `.ui` rewrite below — a one-off dialog, not the main page.
- `MergeConflictResolveWindow.ui` — Qt Designer file for
  `ConflictResolutionDialog`'s table + button layout, loaded at runtime by
  `conflict_dialog.py` the same `QUiLoader` way `submit_section.ui` is
  loaded by the main page — see "Merge conflict resolution" below.
- `conflict_dialog.py` — `ConflictResolutionDialog`: per-file (not
  per-line) keep-ours/keep-theirs resolution, shown when a pull hits a
  merge conflict — see "Merge conflict resolution" below.
- `git_stream_worker.py` — `GitStreamWorker`: generic `QThread` that
  streams a git command's output line-by-line and emits whatever it
  returns via `finished_ok`. Used for Sync's `open_or_sync` (clone/pull,
  triggered only by the Sync button — see above), the pull
  and push steps of the commit workflow, Stage/Unstage/Revert (so a large
  multi-selection can't freeze the UI thread), and the diagnostics check —
  one generic worker covers every fire-and-forget git action on this page.
- `status_worker.py` — `RepoStatusWorker`: fetches working-tree status
  (`RepoStatus`, including the per-file `FileChange` lists — see
  "Where FileChange comes from" below) off the UI thread.
- `commit_log_worker.py` — `CommitLogWorker(QThread)`: fetches this
  machine's local commit log and the not-yet-pulled-in commits on
  `origin/<branch>` off the UI thread, then best-effort backfills avatars
  from a single GitHub API call — see "Commit history panels (Local /
  New)" below.

## Loading the `.ui` file

`RepoGitStatusPage.__init__` calls a module-level `_load_ui_form()` that
loads `submit_section.ui` via `QUiLoader` + `QFile`, resolved with
`Path(__file__).resolve().parent / "submit_section.ui"` (never
`api.app_root / "plugins" / ...` — see the plugin-authoring pitfall about
hardcoded plugin roots breaking on a future `plugins/` reorg). This is a
runtime load, not a `pyside6-uic`-compiled `.py` — editing the `.ui` in
Designer and restarting the app is enough, no build step. The `.ui` only
uses stock Qt widget classes (`QTableView`, `QPlainTextEdit`, `QPushButton`,
`QGroupBox`, plain layouts), so no promoted-widget registration is needed.

`_setup_ui_widgets()` looks up every named widget via
`self._ui.findChild(WidgetClass, "objectName")` and caches it as a `self.*`
attribute, then does all behavior wiring from Python — button `.clicked`
connections, table `setModel`/selection-mode/column-resize configuration,
context menus. The `.ui` file itself declares widgets bare (no
properties beyond labels/read-only flags) precisely so this behavior stays
in version-controlled Python, not scattered across Designer XML.

The loaded `Form` widget is wrapped in `wrap_scrollable(...)` (a
`plugin_api` helper, kept from before this rewrite) so a window-height
squeeze shrinks scroll content instead of collapsing a group box to 0
height — same shape as `project_editor/custom_paths_settings_page.py`.
`self.empty_label`/`self.content_widget` still toggle via `show_exclusive`
for the no-repo-selected state, unchanged from before.

**No custom widget subclasses remain in this plugin.** The pre-rewrite
`LogPanel(QPlainTextEdit)` and `RepoStatusDot(QLabel)` classes are gone —
`plainTextEdit_git_log` (from the `.ui`) is driven by a private
`_append_log(text)` method instead of a subclass, and `self.status_dot` is
a plain `QLabel` updated by a private `_set_status_dot_state(state)`
method. Modified/Staged are `QStandardItemModel`-backed `QTableView`s
instead of the old checkable-`QListWidgetItem` pattern. This was a
deliberate choice (not just incidental to the `.ui` move) to avoid the
class of UI bugs bespoke widget subclasses tend to accumulate — stick to
this when extending the page further.

## Where `FileChange` comes from

`GitService.get_status(repo_path) -> RepoStatus` (re-exported via
`plugin_api`) now returns `unstaged_changes`/`staged_changes:
list[FileChange]` instead of flat path lists. `FileChange` (`path`,
`change_type` — `"untracked"|"added"|"modified"|"deleted"|"renamed"`) is
parsed from git's porcelain status codes in
`GitService._parse_status_porcelain` (`core/vcs/git_service.py`) — added
specifically so Modified/Staged rows can show what kind of change each file
has, which the old flat-path `RepoStatus.untracked/modified/staged` fields
couldn't express. `unstaged_changes` merges untracked files
(`change_type="untracked"`) with working-tree modifications/deletions of
already-tracked files; `staged_changes` reflects the index against HEAD.
`GitService.get_working_tree_status` (the other, older, tuple-returning
entry point) is unchanged in contract — it derives its legacy
`tuple[list[str], list[str], list[str]]` from the same parse.

## Modified / Staged tables

Both are `QTableView`s (`tableView_modified`/`tableView_staged` in the
`.ui`) backed by a `QStandardItemModel` with three columns: **File Name**
(`PurePosixPath(path).name`), **File Path** (the path's parent directory,
relative to repo root — empty string for a repo-root file), **Modified**
(display text from `FileChange.change_type`: `untracked`/`added` →
"Added", `modified` → "Modified", `deleted` → "Removed", `renamed` →
"Renamed"). The real relative path and raw `change_type` are stashed on
each row's File Name item via `Qt.UserRole`/`Qt.UserRole + 1`
(`_PATH_ROLE`/`_CHANGE_TYPE_ROLE`) so display formatting never has to be
reverse-parsed. Both tables use `ExtendedSelection` + `SelectRows`, so
**Stage**, **Unstage** (labelled "Unstage" in the `.ui`, this is the old
"Restore"/unstage-from-index button), and **Revert** all act on whatever
rows are currently selected (`_selected_rows_data`), reading multiple rows
at once instead of the old per-item checkbox/"Select All" pattern (removed
entirely — multi-selection replaces it). Revert splits its selection by
`change_type == "untracked"` vs tracked to call
`GitService.revert_paths(modified_paths=..., untracked_paths=...)`
correctly, same split logic as before but driven by `change_type` instead
of cross-referencing `self._last_status.untracked`. All three actions run
through `GitStreamWorker` (Stage always did; Unstage/Revert now do too, so
a large multi-selection can't freeze the UI thread).

**"Submit All Staged"** (`pushButton_submit_all_staged` — the old "Pull and
Push" button) is unconditional: it always acts on every currently staged
file, ignoring table selection, exactly as before.

Right-click on a row still offers "Inspect in Explorer" (jumps to Explorer
via `browse_file_requested`), scoped to the row under the cursor.

## Explorer refresh after Sync

Cloning/pulling files onto disk (Sync New Commit) doesn't switch the
active repo, so nothing else would ever tell Explorer's
`QFileSystemModel`-backed file table to rescan — its own filesystem watcher
can miss or lag a bulk change like a git clone/pull, which used to mean the
Explorer tab stayed stale until the user manually reopened it or restarted
the app. `plugin.py`'s `_wire` connects `page.sync_finished` to
`UICommandService.refresh_section("repo_browser")`
(`plugin_api/registries/section_registry.py`), which looks Explorer's page
up by its `SectionRegistry` key and calls its optional `refresh_content()`
method (`interface/page_protocols.py`'s `RefreshablePage` protocol) if it
implements one — without switching the visible tab, unlike
`navigate_and_focus`. See `plugins/core/explorer/repo_browser_page.py`'s
`refresh_content()` for what Explorer actually does with this. Only wired
to `sync_finished` (the Sync button's clone/pull), not the commit→pull→push
workflow's own pull step — that wasn't reported as stale; extend the same
`refresh_section` call there too if it turns out to need it.

## Diagnostics table (`tableView_git_status`)

New in this rewrite. Lives in the "Git Log" group box (`groupBox_5`),
alongside `plainTextEdit_git_log` and the Open Local Directory/Open Repo
Site buttons — originally its own "Status" tab next to a "Log" tab (the
`.ui` had a `tabWidget` at the time), since folded into one flat group box
when the 2026-08-22 commit-history split reorganized the page into the
current Modified/Staged row plus New Commit to Sync/Local Commit/Git Log
row, with no tabs left anywhere on the page. Three fixed rows, refreshed
by `_run_diagnostics()` on every `refresh_status()` call (Sync, Refresh
Status, repo switch — same trigger set as everything else on this
page), run through `GitStreamWorker` like every other background action
here (no dedicated worker class):

- **Token & Auth** — `GitService.get_github_token()` present, and if the
  remote parses as a GitHub URL, also `check_repo_access(owner, name,
  token)` (the exact primitive `start_sync`'s pre-flight access check
  already uses).
- **Clone** — `GitService.is_cloned(dest_path)` (the same `.git`-directory
  check `refresh_status` already does before doing anything else).
- **Up-to-date** — a bounded `GitService.fetch()` then
  `GitService.get_ahead_behind(dest_path)`; behind-by-N → warning row
  ("N commits behind — sync to update"); otherwise a pass row ("Up to
  date" or "Up to date locally, N commits ahead (not yet pushed)").

All three checks reuse existing `GitService`/`core/vcs/repo_access.py`
primitives — no `core/` change was needed for this table (only for the
`FileChange` per-file typing above). Columns: **Name**, **Detail** (free
text per above), **Status** (icon-only —
`self.style().standardIcon(QStyle.SP_DialogApplyButton)` on pass,
`QStyle.SP_MessageBoxWarning` on fail, via `QStandardItem.setIcon`).

This table is deliberately independent of the sidebar status dot below —
they answer different questions (working-tree cleanliness vs. auth/clone/
staleness) and don't share state.

## Commit history panels (Local / New)

Split (2026-08-22) into two side-by-side tables, each its own `QGroupBox`
in the `.ui` — `tableView_local_commit_history` ("Local Commit": this
machine's own local git log, i.e. `HEAD`) and `tableView_new_commit_history`
("New Commit to Sync", next to `pushButton_sync`, now labelled "Sync New
Commit": commits already sitting on `origin/<branch>` that this clone
hasn't pulled in yet — teammates' work "Sync New Commit" would bring in).
Previously a single `tableView_commit_history` fed by a GitHub-API-first
whole-repo activity feed; that feed had no way to express a
`HEAD..origin/<branch>` revision range, so both lists are now built from
local git instead (see "How it fetches" below). Avatars are still
backfilled afterward from one GitHub API call, matched by commit hash — see
`CommitLogWorker._backfill_avatars` — so a commit GitHub's feed doesn't
cover (not a github.com remote, offline, rate-limited, unpushed-local-only,
or old enough to have fallen off the fetched page) falls back to the 👤
glyph rather than showing nothing.

Both tables are backed by their own 4-column `QStandardItemModel` (avatar
icon, Author, Message, Time), built by the shared
`_setup_commit_log_table(table, entries_key)` helper (`entries_key` is
`"local"` or `"new"`). The Time column merges what used to be separate Time
Ago/Date columns via the page's own `_format_commit_time(raw)` — relative
(`format_relative_time`, e.g. "3 days ago") for commits inside
`_RELATIVE_TIME_CUTOFF_DAYS` (7), otherwise absolute (`format_commit_date`,
e.g. "15 Jan 2024"); both formatters still come from
`interface/shared/commit_history.py`.
Double-clicking a row in either table opens
`interface/shared/commit_history.py`'s `CommitFilesDialog`, passing
`git_service`/`repo_path`/`on_browse_file` — its "Browse" button jumps
straight to Explorer via the same `browse_file_requested` signal the
Modified/Staged tables' "Inspect in Explorer" context menu uses.
`self._commit_log_entries` is a `{"local": [...], "new": [...]}` dict (not
a flat list, since a double-click on either table needs to look its row up
in the matching half) so it can map a table row back to its
`CommitHistoryEntry`.

- **When it polls**: `_poll_commit_log` runs on every `refresh_status()`
  call (repo switch, the Refresh Status button, and Sync —
  `_on_push_finished` already calls `refresh_status()`
  too, so a just-pushed commit shows up immediately), plus a background
  `QTimer` every `COMMIT_LOG_POLL_INTERVAL_MS` (30 minutes) so it stays
  current while the tab just sits open.
- **How it fetches**: `CommitLogWorker` (a `QThread`) runs
  `GitService.fetch()` first (bounded — `timeout=30`, so a stalled network
  fetch can't hang this background poll forever) — remote-tracking refs
  only, never the working tree — then makes two local `GitService.get_commit_log`
  calls: one plain (`ref=None` → `HEAD`) for the local list, one with
  `ref=f"HEAD..origin/{branch}"` for the new/unsynced list (empty if there's
  no upstream yet, or nothing new — `get_commit_log` itself swallows
  `GitOperationError` and returns `[]`), then one `fetch_entries_via_github`
  call (same GitHub commits API `interface/shared/commit_history.py`'s
  other callers use) to backfill avatars by hash — best-effort, `None`/empty
  result just leaves every entry on the 👤 fallback.
  `self._commit_log_avatar_cache` lives on the page (not the worker — passed
  in as `avatar_cache` so it survives across polls) so an avatar is only
  ever downloaded once across the page's whole lifetime, not re-fetched
  every 30-minute repoll. `entries_ready` emits
  `(local_entries, new_entries)` — both lists together, always in that
  order.
- **No dedup/unread tracking**: each panel just re-renders whatever the
  latest fetch returns (newest first, capped at 20).

## Other Command buttons

Inside the "Git Log" group box (`groupBox_5`, alongside the diagnostics
table and `plainTextEdit_git_log`) in the `.ui`:
- **Open Local Directory** (`pushButton_local_dir`) — `open_in_file_explorer(dest_path)`
  (`core/os_utils.py`, re-exported via `plugin_api`; wasn't used by this
  plugin before this rewrite).
- **Open Repo Site** (`pushButton_repo_website`) — same behavior as the old
  "GitWeb" button: parses the remote as a GitHub URL and opens
  `https://github.com/<owner>/<repo>` in the system browser; warns if the
  remote isn't a github.com URL.

## Merge conflict resolution

`ConflictResolutionDialog` (`conflict_dialog.py`) loads
`MergeConflictResolveWindow.ui` at runtime (same `QUiLoader` idiom as
`submit_section.ui` — see "Loading the .ui file" above) and populates its
one widget, `tableWidget_conflict_info` (a plain `QTableWidget`, column
count/headers set in Python since the `.ui` declares it bare), one row per
conflicted file (`GitService.get_conflicted_files`). Seven columns: File,
My Avatar, My Username, My Status, Other Avatar, Other Username, Other
Status.

Two different pulls can leave a real merge conflict (`MERGE_HEAD` present)
behind — the Submit workflow's own pull step, and Sync's `open_or_sync`
(2026-08-22: previously Sync's failure path just showed the raw git error
in a plain "Sync Failed" box with no conflict handling at all, even for a
real conflict). Both now go through the same
`_resolve_merge_conflict(dest_path)` (`repo_git_status_page.py`) — shows
the dialog, applies `resolve_conflict_file`/`complete_merge` on accept,
returns whether the merge got completed. `_on_pull_step_failed` chains into
`_start_push_step()` afterward (matching the commit→pull→push workflow);
`_on_sync_failed` instead calls `_on_sync_finished("merged")` (there's no
push step to chain into for a plain sync). Checked via
`GitService.has_unresolved_merge` (`MERGE_HEAD` existence) before showing
the dialog either way — a pull can also fail for unrelated reasons (auth,
network, or git refusing to merge at all e.g. "untracked working tree
files would be overwritten by merge") that leave no `MERGE_HEAD` and so
still fall through to the plain error box, since there's nothing
`get_conflicted_files` would find to resolve.

- **"Mine"** is always the signed-in user — `my_username` is
  `local_config_store.github_username`, passed in by the caller; the avatar
  is one `fetch_avatar_bytes(username)` call (`core_api`, re-exported via
  `plugin_api` — hits the public `github.com/<user>.png` URL directly, no
  API token/rate limit). Same for every row.
- **"Other"** is per-file — whoever last touched that specific file on the
  incoming side, since a single pull's conflicts can span commits from
  different teammates. `_fetch_other_author` tries
  `fetch_entries_via_github(..., relative_path=file_path, limit=1, page=1,
  ...)` first (GitHub-API-first, path-scoped — the top result is exactly
  the most recent commit on the remote's default branch touching this
  file, i.e. `MERGE_HEAD`'s version of it) for both username and avatar;
  falls back to `GitService.get_commit_log(repo_path, limit=1,
  ref="MERGE_HEAD", paths=[file_path])` (local-git-only, author name but no
  avatar — added `paths` support to `get_commit_log` for exactly this
  lookup, see its docstring) when the repo isn't GitHub-hosted, is offline,
  or the API call fails.
- Both fetches run once, together, off the UI thread via one
  `GitStreamWorker` (`_start_author_fetch`/`_fetch_author_info`) — rows are
  populated immediately with File/My Username (already known locally, no
  I/O) and a "Loading..." placeholder for Other Username, then patched in
  place once the worker reports back. Choose Mine/Choose Other stay
  disabled until then.
- **Multi-selection**: `ExtendedSelection` + `SelectRows`, so Choose
  Mine/Choose Other act on every currently selected row, not just one —
  `_apply_choice` sets the check icon (`QStyle.SP_DialogApplyButton`) on
  the chosen side's Status cell and the cross icon
  (`QStyle.SP_DialogCancelButton`) on the other side's, for each selected
  row, and records `file_path -> "ours"|"theirs"` in `self._resolutions`.
  "Resolve Conflict and Sync" (`pushButton_resolve_and_sync`) stays
  disabled until every conflicted file has a resolution — same
  all-resolved gating the previous radio-button dialog had.
- `resolutions() -> dict[str, str]` keeps the same `"ours"`/`"theirs"`
  contract `_resolve_merge_conflict` already expects
  (`GitService.resolve_conflict_file`'s `keep` argument) — only the
  dialog's constructor call changed (now needs
  `git_service`/`repo_path`/`github_token`/`my_username` alongside
  `conflicted_files`).

## Sidebar status dot

`plugin_api/registries/section_registry.py`'s `SectionSpec.trailing_widget_factory`
(a general-purpose slot any section can use for a small status widget at
the right edge of its own sidebar row) is handed `page.status_dot` (a plain
`QLabel`) in `plugin.py`. `RepoGitStatusPage` owns/updates it directly via
`_set_status_dot_state` — `SectionTabList` only lays it out.

Three states, driven entirely by the existing `refresh_status()` call (Sync,
Refresh Status, and repo switch — no extra polling
or network calls added for this). Icons are built-in Qt standard icons
(`QStyle.standardIcon`):
- **loading** (hidden, no icon) — a status check is in flight, or the last
  one is more than 10 minutes stale. `refresh_status()` sets this
  immediately on every call, before the new `RepoStatusWorker` reports back,
  so the dot never shows a stale/wrong-repo icon mid-check.
- **dirty** (`QStyle.SP_MessageBoxWarning`) — `_on_status_ready` saw a
  non-clean `RepoStatus` (unstaged or staged changes present).
- **fresh** (`QStyle.SP_DialogApplyButton`) — `_on_status_ready` saw a clean
  `RepoStatus`. Only valid for `FRESHNESS_WINDOW_MS` (10 minutes) —
  `_freshness_timer` (restarted on every `refresh_status()` call) flips it
  back to **loading** once that verification goes stale, rather than
  claiming a possibly-outdated "clean" forever between manual
  refreshes/syncs.

There is deliberately no "would conflict on push" state on this dot — that
question is what the diagnostics table's Up-to-date row answers instead.

**Working here:** stay inside this folder unless the change needs a new
`core_api`/`plugin_api` primitive (see "Where `FileChange` comes from"
above for the precedent — extend `core/models.py` +
`core/vcs/git_service.py`, then re-export through `core_api` and
`plugin_api`, then update `core-api.md`/`plugin-api.md`), an
`interface/shared/` addition, or touches `interface/main_window.py`'s
generic `UICommandService` wiring.
