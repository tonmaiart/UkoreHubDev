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
  `background_threads` (reaches into `page._git_worker`/`_status_worker`/
  `_stream_worker`/`_commit_log_worker` for `MainWindow.closeEvent`'s
  shutdown cleanup) and
  `wire` — connects `sync_started`/`sync_finished`/`sync_failed` to
  `UICommandService.set_status_message` (the sidebar status line) and
  `browse_file_requested` to `UICommandService.navigate_and_focus` (jumps to
  Explorer's `"repo_browser"` section key and calls its optional
  `browse_to_path` protocol method — see
  `plugins/core/explorer/repo_browser_page.py`). See
  `plugin_api/registries/section_registry.py`'s `UICommandService` for why
  this is a fixed set of named callbacks rather than a generic dispatcher.
- `repo_git_status_page.py` — `RepoGitStatusPage`: the top-level Submit
  page. Drives the full sync/commit/pull/push workflow via the workers
  below, and shows the Modified/Staged lists. Both lists' items are
  checkable (`Qt.ItemIsUserCheckable`, `NoSelection` mode) rather than
  row-selected — `_checked_paths(list_widget)` reads whichever items are
  ticked, and Stage/Revert (Modified) and Restore (Staged) act on that set,
  so multiple files can be picked without holding Ctrl/Shift. Each panel
  has its own "Select All" button (`self.select_all_button` for Modified,
  `self.staged_select_all_button` for Staged), both wired to the shared
  `_on_select_all_clicked(list_widget)` — it toggles every item in that
  list to checked, or back to unchecked if all were already checked. The
  Sync/Refresh Status buttons
  live under the log panel inside a "Git Log" `QGroupBox`, matching the
  Modified/Staged panel styling. Below that, a "Commit History" `QGroupBox`
  shows the whole repo's recent commits (every teammate's pushes, not just
  this machine's own) — see "Commit history panel" below. Implements the
  optional
  `sync_active_repo(...)` protocol method —
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
  checkbox), shown before the pull→push workflow starts.
- `conflict_dialog.py` — `ConflictResolutionDialog`: per-file keep-ours/
  keep-theirs resolution, shown when a pull hits a merge conflict.
- `log_panel.py` — `LogPanel`: scrolling read-only log output during
  sync/push/pull.
- `git_stream_worker.py` — `GitStreamWorker`: generic `QThread` that
  streams a git command's output line-by-line and emits whatever it
  returns via `finished_ok`. Used for the Sync button's `open_or_sync`
  (clone/pull, also driving `sync_active_repo`'s launch/repo-switch
  auto-sync) as well as the pull and push steps of the commit workflow —
  one generic worker where there used to be a separate `GitWorker` class
  just for `open_or_sync`.
- `status_worker.py` — `RepoStatusWorker`: fetches working-tree status
  (modified/staged/untracked) off the UI thread.
- `status_dot.py` — `RepoStatusDot(QLabel)`: the small status icon shown
  at the right edge of Submit's own sidebar row — see "Sidebar status dot"
  below.
- `commit_log_worker.py` — `CommitLogWorker(QThread)`: fetches the whole
  repo's most recent commits off the UI thread (GitHub-API-first,
  local-git-fallback via `interface/shared/commit_history.py`'s
  `fetch_entries_via_github`) — see "Commit history panel" below.

## Commit history panel

`RepoGitStatusPage` renders a whole-repo commit history directly on this
tab, as a plain `QTableWidget` (`self.commit_log_table`, columns avatar
icon/Author/Message/Time Ago/Date — relative time before absolute date,
since relative is the one worth reading at a glance) — deliberately *not*
the `CommitCard` template `plugins/core/explorer/`'s per-path panel uses
(see "Card→table rewrite, 2026-08-13" below for why). The avatar column
reuses `CommitHistoryEntry.avatar_bytes` (rendered via `QTableWidgetItem.setIcon`,
falling back to the same 👤 glyph `CommitCard` uses when there's no avatar)
and `format_relative_time` (`interface/shared/commit_history.py`, alongside
`format_commit_date`) backs the Time Ago column. `self._commit_log_avatar_cache`
lives on the page (not the worker) so avatars are only ever downloaded once
across the page's whole lifetime, not re-fetched on every 30-minute repoll —
passed into `CommitLogWorker`'s `avatar_cache` param, same idiom
`PathCommitHistoryPanel`'s `_avatar_cache` uses for Explorer. Unlike
Explorer's panel (scoped to whichever path is selected in Repo Browser),
this one always shows the active repo's history as a whole. Double-clicking
a row opens
`interface/shared/commit_history.py`'s `CommitFilesDialog` (the same popup
CommitCard's own "Files" button uses) via `_on_commit_row_double_clicked`,
passing `git_service`/`repo_path`/`on_browse_file` — its "Browse" button
jumps straight to Explorer via the same `browse_file_requested` signal the
Modified/Staged lists' "Inspect in Explorer" context menu already uses.
`self._commit_log_entries` keeps the last-fetched list around so a
double-click can map a table row back to its `CommitHistoryEntry`.

- **When it polls**: `_poll_commit_log` runs on every `refresh_status()`
  call (repo switch, the Refresh Status button, and auto-sync on
  launch/repo-switch — `_on_push_finished` already calls `refresh_status()`
  too, so a just-pushed commit shows up immediately), plus a background
  `QTimer` every `COMMIT_LOG_POLL_INTERVAL_MS` (30 minutes) so it stays
  current while the tab just sits open.
- **How it fetches**: `CommitLogWorker` (a `QThread`) runs
  `GitService.fetch()` first (bounded — `timeout=30` passed down to
  `GitService._run_capture`, so a stalled network fetch can't hang this
  background poll forever) — remote-tracking refs only, never the working
  tree, so it's safe to run silently in the background — then reads recent
  commits the same GitHub-API-first/local-git-fallback way
  `interface/shared/commit_history.py`'s other callers do (`origin/<branch>`
  when falling back to local, so commits nobody has pulled into this clone
  yet still show up; if that ref doesn't exist either — e.g. an unpushed
  branch — falls back again to plain local `HEAD`, same as Explorer's
  panel, instead of showing nothing).
- **No dedup/unread tracking**: unlike the old Notification-tab team
  activity feed this replaced, the panel just re-renders whatever the
  latest fetch returns (newest first, capped at 20) — there's no
  persisted "last seen commit" bookkeeping, since this is a plain
  browse-the-history panel, not a notification stream.
- **Card→table rewrite, 2026-08-13**: the original `CommitCard`-based
  version had two real bugs, found while debugging "Explorer's panel shows
  history, Submit's doesn't": (1) `CommitCard`/`CommitHistoryEntry` were
  used in `repo_git_status_page.py` without ever being imported — every
  render with a non-empty `entries` list threw `NameError` inside the
  `entries_ready` slot, silently aborting before any card was added; (2)
  `commit_log_group` was the only widget in `content_layout` given a
  stretch factor, and the page's own content wasn't wrapped in a
  `wrap_scrollable(...)` the way sibling pages are — under vertical space
  pressure Qt shrinks the highest-stretch item first, so the whole group
  box (border and title included) could be squeezed to 0 height rather
  than just showing fewer cards. The page content is now wrapped in
  `wrap_scrollable(...)` (`scroll`/`content_wrap_layout`, same shape as
  `project_editor/custom_paths_settings_page.py`) as a general fix for (2),
  and the plain table replaces `CommitCard` entirely for (1) plus the
  user's ask to drop the avatar-badge styling here in favor of a plain
  data table — Explorer's per-path panel is untouched and still uses
  `CommitCard`.

## Sidebar status dot

`plugin_api/registries/section_registry.py`'s `SectionSpec.trailing_widget_factory`
(a general-purpose slot any section can use for a small status widget at
the right edge of its own sidebar row) is handed `page.status_dot` in
`plugin.py`. `RepoGitStatusPage` owns/updates it directly — `SectionTabList`
only lays it out.

Three states, driven entirely by the existing `refresh_status()` call (Sync,
Refresh Status, and the auto-sync on launch/repo-switch — no extra polling
or network calls added for this). Icons are built-in Qt standard icons
(`QStyle.standardIcon`, migrated 2026-08-13 from a QSS `setProperty("state",
...)` + `unpolish`/`polish` repaint — see `interface.md`'s Zero QSS Policy
section), not colored dots anymore:
- **loading** (hidden, no icon) — a status check is in flight, or the last
  one is more than 10 minutes stale. `refresh_status()` sets this
  immediately on every call, before the new `RepoStatusWorker` reports back,
  so the dot never shows a stale/wrong-repo icon mid-check.
- **dirty** (`QStyle.SP_MessageBoxWarning`) — `_on_status_ready` saw a
  non-clean `RepoStatus` (untracked/modified/staged present).
- **fresh** (`QStyle.SP_DialogApplyButton`) — `_on_status_ready` saw a clean
  `RepoStatus`. Only valid for `FRESHNESS_WINDOW_MS` (10 minutes) —
  `_freshness_timer` (restarted on every `refresh_status()` call) flips it
  back to **loading** once that verification goes stale, rather than
  claiming a possibly-outdated "clean" forever between manual
  refreshes/syncs.

There is deliberately no "would conflict on push" state — detecting that
would need a new `git fetch` this page doesn't otherwise do; left out of
scope for now.

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive, an `interface/shared/` addition, or touches
`interface/main_window.py`'s generic `UICommandService` wiring.
