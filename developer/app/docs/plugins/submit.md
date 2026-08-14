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
  `UICommandService.set_status_message` (the sidebar status line) and
  `browse_file_requested` to `UICommandService.navigate_and_focus` (jumps to
  Explorer's `"repo_browser"` section key and calls its optional
  `browse_to_path` protocol method — see
  `plugins/core/explorer/repo_browser_page.py`). See
  `plugin_api/registries/section_registry.py`'s `UICommandService` for why
  this is a fixed set of named callbacks rather than a generic dispatcher.
- `submit_section.ui` — Qt Designer file for the whole page, loaded at
  runtime by `RepoGitStatusPage` via `PySide6.QtUiTools.QUiLoader` (see
  "Loading the .ui file" below). Edit this in Designer to change layout/
  labels/spacing — no Python change or rebuild needed, just restart the app.
- `repo_git_status_page.py` — `RepoGitStatusPage`: the top-level Submit
  page. Drives the full sync/commit/pull/push workflow via the workers
  below, and shows the Modified/Staged/diagnostics/commit-history tables.
  Implements the optional `sync_active_repo(...)` protocol method —
  `interface/main_window.py`'s `_start_auto_sync` calls this generically
  on launch/repo-switch, combining `set_repo()` + `start_sync()`. Before the
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
- `conflict_dialog.py` — `ConflictResolutionDialog`: per-file keep-ours/
  keep-theirs resolution, shown when a pull hits a merge conflict. Also
  untouched.
- `git_stream_worker.py` — `GitStreamWorker`: generic `QThread` that
  streams a git command's output line-by-line and emits whatever it
  returns via `finished_ok`. Used for Sync's `open_or_sync` (clone/pull,
  also driving `sync_active_repo`'s launch/repo-switch auto-sync), the pull
  and push steps of the commit workflow, Stage/Unstage/Revert (so a large
  multi-selection can't freeze the UI thread), and the diagnostics check —
  one generic worker covers every fire-and-forget git action on this page.
- `status_worker.py` — `RepoStatusWorker`: fetches working-tree status
  (`RepoStatus`, including the per-file `FileChange` lists — see
  "Where FileChange comes from" below) off the UI thread.
- `commit_log_worker.py` — `CommitLogWorker(QThread)`: fetches the whole
  repo's most recent commits off the UI thread (GitHub-API-first,
  local-git-fallback via `interface/shared/commit_history.py`'s
  `fetch_entries_via_github`) — see "Commit history panel" below.

## Loading the `.ui` file

`RepoGitStatusPage.__init__` calls a module-level `_load_ui_form()` that
loads `submit_section.ui` via `QUiLoader` + `QFile`, resolved with
`Path(__file__).resolve().parent / "submit_section.ui"` (never
`api.app_root / "plugins" / ...` — see the plugin-authoring pitfall about
hardcoded plugin roots breaking on a future `plugins/` reorg). This is a
runtime load, not a `pyside6-uic`-compiled `.py` — editing the `.ui` in
Designer and restarting the app is enough, no build step. The `.ui` only
uses stock Qt widget classes (`QTableView`, `QPlainTextEdit`, `QPushButton`,
`QGroupBox`, `QTabWidget`, plain layouts), so no promoted-widget
registration is needed.

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

## Diagnostics table (`tableView_git_status`)

New in this rewrite. Lives in the "Status" tab (`.ui`'s `tabWidget`,
alongside a "Log" tab holding `plainTextEdit_git_log` — the old combined
Sync/Refresh/GitWeb button row plus log view). Three fixed rows, refreshed
by `_run_diagnostics()` on every `refresh_status()` call (Sync, Refresh
Status, repo switch/auto-sync — same trigger set as everything else on this
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

## Commit history panel

`tableView_commit_history`, backed by a 5-column `QStandardItemModel`
(avatar icon, Author, Message, Time Ago, Date — relative time before
absolute date, since relative is the one worth reading at a glance). Same
data/behavior as before this rewrite, just targeting a `QTableView` +
`QStandardItemModel` instead of a hand-built `QTableWidget`. The avatar
column reuses `CommitHistoryEntry.avatar_bytes` (rendered via
`QStandardItem.setIcon`, falling back to a 👤 glyph when there's no
avatar) and `format_relative_time`/`format_commit_date`
(`interface/shared/commit_history.py`). `self._commit_log_avatar_cache`
lives on the page (not the worker) so avatars are only ever downloaded once
across the page's whole lifetime, not re-fetched on every 30-minute repoll.
Double-clicking a row opens `interface/shared/commit_history.py`'s
`CommitFilesDialog`, passing `git_service`/`repo_path`/`on_browse_file` —
its "Browse" button jumps straight to Explorer via the same
`browse_file_requested` signal the Modified/Staged tables' "Inspect in
Explorer" context menu uses. `self._commit_log_entries` keeps the
last-fetched list around so a double-click can map a table row back to its
`CommitHistoryEntry`.

- **When it polls**: `_poll_commit_log` runs on every `refresh_status()`
  call (repo switch, the Refresh Status button, and auto-sync on
  launch/repo-switch — `_on_push_finished` already calls `refresh_status()`
  too, so a just-pushed commit shows up immediately), plus a background
  `QTimer` every `COMMIT_LOG_POLL_INTERVAL_MS` (30 minutes) so it stays
  current while the tab just sits open.
- **How it fetches**: `CommitLogWorker` (a `QThread`) runs
  `GitService.fetch()` first (bounded — `timeout=30`, so a stalled network
  fetch can't hang this background poll forever) — remote-tracking refs
  only, never the working tree — then reads recent commits the same
  GitHub-API-first/local-git-fallback way `interface/shared/commit_history.py`'s
  other callers do.
- **No dedup/unread tracking**: the panel just re-renders whatever the
  latest fetch returns (newest first, capped at 20).

## Other Command buttons

Below the Commit History group in the `.ui`:
- **Open Local Directory** (`pushButton_local_dir`) — `open_in_file_explorer(dest_path)`
  (`core/os_utils.py`, re-exported via `plugin_api`; wasn't used by this
  plugin before this rewrite).
- **Open Repo Site** (`pushButton_repo_website`) — same behavior as the old
  "GitWeb" button: parses the remote as a GitHub URL and opens
  `https://github.com/<owner>/<repo>` in the system browser; warns if the
  remote isn't a github.com URL.

## Sidebar status dot

`plugin_api/registries/section_registry.py`'s `SectionSpec.trailing_widget_factory`
(a general-purpose slot any section can use for a small status widget at
the right edge of its own sidebar row) is handed `page.status_dot` (a plain
`QLabel`) in `plugin.py`. `RepoGitStatusPage` owns/updates it directly via
`_set_status_dot_state` — `SectionTabList` only lays it out.

Three states, driven entirely by the existing `refresh_status()` call (Sync,
Refresh Status, and the auto-sync on launch/repo-switch — no extra polling
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
