# plugins/core/explorer/

Moved here (2026-08-13) from `app/plugins/core/explorer/README.md`. See
`plugins-guide.md` for the general plugin-authoring conventions this
plugin follows.

The Explorer tab (`SectionRegistry` key `repo_browser`) — browse a cloned
repo's files, with a Miller-column Folder Navigator and a per-path commit
history panel. A real always-on `plugins/core/` plugin — not
special-cased by `interface/`, registers into `SectionRegistry` the same
way any other plugin would. (Recent Files and Favorites used to live in a
left sidebar here — removed for a cleaner Explorer; the Up/Back nav
buttons at the top of the file table are the only navigation aids now.)

- `explorer_section.ui` — Qt Designer source for the whole tab (nav row,
  Miller-column grid, file table, File History panel, Last Opened/Bookmarks
  side panel). `browser_widget.py` loads this at runtime via `QUiLoader`
  instead of building the layout in code — edit the layout in Designer
  (`objectName`s: `pushButton_back`/`pushButton_up`/`pushButton_refresh`/
  `pushButton_create_folder`/`pushButton_open_current_directory`,
  `lineEdit_path`, `lineEdit_search`, `listWidget_column_1..5` +
  `lineEdit_column_1..5_search`, `tableWidget_current_directory`,
  `listWidget_last_opened_file`, `listView_bookmarks`, `groupBox_5` (empty
  container the commit panel gets added into at runtime)) without touching
  Python. `RepoBrowserWidget.__init__` binds each widget via
  `self.ui.findChild(Type, "objectName")` and wires signals exactly as it
  did before — renaming an `objectName` in the `.ui` breaks that binding
  silently (findChild returns `None`, later attribute access raises), so
  grep `browser_widget.py` for the old name when renaming one in Designer.
- `manifest.json` — plugin id `explorer`, entry point `plugin.py`.
- `plugin.py` — `register(api)`: constructs `RepoBrowserPage` from
  `api.local_config`/`api.git`/`api.file_opener_registry`, registers it as
  the `SectionSpec(key="repo_browser", order=10, ...)` section. Also wires
  `background_threads` (for `MainWindow.closeEvent`'s shutdown cleanup) —
  reaches into `page.browser.commit_panel._worker`. (Used to also register
  an `ExplorerSettingsPage`/"Add Pinned Repo..." `CATEGORY_REPO` Settings
  tab and a `pinned_repo_browser_page.py` dynamic-tab page — the whole
  pinned-repo feature was removed as no longer needed; see git history if
  it needs to come back.)
- `repo_browser_page.py` — `RepoBrowserPage`: the top-level Explorer page.
  Owns file-open delegation (`core/extensibility/file_opener.py`'s
  `FileOpenerRegistry`, so a plugin can claim an extension) and implements
  the optional `browse_to_path(path)` protocol method (see
  `plugin_api/registries/section_registry.py`'s `UICommandService`) —
  `plugins/core/submit/` calls into this generically via `MainWindow`'s
  `navigate_and_focus`, not by importing this module directly.
  `browse_to_path` delegates straight to `browser_widget.py`'s
  `browse_to_file(path)`, which — like `_on_last_opened_clicked`/
  `_on_bookmark_clicked`/the breadcrumb's typed-file case below —
  navigates to the file's parent folder and selects the file's own row
  (`_select_file_in_table`) rather than just opening the folder. If the
  path no longer exists on disk (e.g. the commit's file was since deleted
  or moved), it shows a `QMessageBox.warning` instead of navigating. Also
  implements the optional `refresh_content()` protocol method
  (`interface/page_protocols.py`'s `RefreshablePage`, called via
  `UICommandService.refresh_section("repo_browser")`) — Submit's "Sync
  Others Commit" button calls into this after every sync so the file table
  doesn't sit stale until the user manually reopens the tab or restarts the
  app (the file table is only rebuilt on an explicit `_navigate_to`, so a
  bulk change like a git clone/pull otherwise wouldn't show up until the
  next navigation). `refresh_content()` re-runs the same
  not-cloned/exists check `set_repo()` does (covers "just cloned for the
  first time", where `browser.set_root()` has never run) — if this page was
  already showing the same repo, `set_repo()`'s
  `repo.id == self._last_repo_id` guard would otherwise skip re-scanning
  entirely, so `refresh_content()` calls `self.browser.reload()` instead in
  that case (covers "pulled more commits into an already-cloned repo").
  `set_repo()` now also stashes `workspace_root` on `self._workspace_root`
  so `refresh_content()` has it to work with without needing its own
  parameter — and, since 2026-08-14, `project.id` on `self._active_project_id`
  (only when `project` is not `None`) for the same reason, so bookmarks
  (see `bookmarks_store.py` below) still have a project id to key off of
  when `refresh_content()`'s fallback calls `set_repo(None, self._active_repo,
  self._workspace_root)`.
- `browser_widget.py` — `RepoBrowserWidget`: the actual browser — a
  Miller-column "Folder Navigator", a sortable/searchable file table with
  Up/Back navigation, and the per-path commit history panel docked to the
  right of the table. `history_back_button` returns to whatever path was
  current before the last navigation (`_back_stack`); `up_button` always
  jumps to the current path's parent regardless of history — different
  semantics, so don't conflate them. Nav buttons are plain text-labeled
  `QPushButton`s (label text authored directly in `explorer_section.ui`,
  e.g. `pushButton_up`'s "▲") — no icon is set from code (removed
  2026-08-20; had briefly gone through a `QStyle.standardIcon`-based
  `_apply_nav_icon` helper migrated 2026-08-13 from 3 bundled-PNG path
  constants that pointed at files which never actually existed in the
  repo, so this had always silently fallen back to text-only buttons
  before anyway; see `interface.md`'s Zero QSS Policy section).
  `add_folder_button` sits right after `up_button` in the nav row and just
  calls `_create_new_folder(self._current_path)` — a toolbar shortcut for
  the same "Create New Folder" action described below.
  A Reload button (`reload_button`) sits right after `add_folder_button` in
  `nav_row` — calls `reload()`, which force-rescans the current folder from
  disk without changing which folder is open or touching navigation
  history. Since the file table is populated directly from `iterdir()` on
  every navigation (see below) rather than a cached filesystem-model
  listing, `reload()` is just a re-navigate to the current path.
  `RepoBrowserPage.refresh_content()` (above) calls this same method for
  the automatic post-sync case — the nav button is the manual escape hatch
  for any other staleness (e.g. a file changed by an external tool while
  Explorer was open).
  Right-clicking a row opens a context menu (Add this to bookmarks/Copy
  Name/Copy File Relative Path/Copy File Absolute Path/Rename/Delete) via
  `_on_table_context_menu`;
  right-clicking blank space in the table (no row under the cursor) falls
  through to `_on_empty_area_context_menu` instead, whose Create New
  Folder/Rename Folder/Delete Folder act on the currently open folder
  (`_current_path`) rather than a selected row — Rename/Delete Folder are
  disabled while `_current_path` is the repo root, since renaming/deleting
  it out from under `set_root()`'s `_last_opened_store` would leave them
  pointed at a path that no longer exists. The file table
  (`tableWidget_current_directory`, a plain `QTableWidget` — 6 columns
  authored directly in `explorer_section.ui`: Name/Size/Date
  Modified/Time Ago/Local Modified/Last Commit) is populated manually
  by `_populate_table`/`_set_row` on every `_navigate_to` (a synchronous
  `iterdir()` + `stat()` per entry, sorted case-insensitively by name) —
  there's no `QFileSystemModel`/proxy backing it anymore, so `reload()` is
  just a re-navigate to the current path rather than a filesystem-watcher
  workaround. Each row's absolute path lives in `Qt.UserRole` on the
  column-0 (Name) item, same convention as the Last Opened/Bookmarks
  tables below — `_path_for_row`/`_row_for_path` are the lookup helpers
  (`_row_for_path` does a linear scan comparing `Path` equality, so it's
  separator-agnostic). Size and Date Modified/Time Ago use a small
  `_SortableItem(QTableWidgetItem)` subclass that sorts by an explicit key
  (byte count / mtime) instead of the displayed text, since "12.3 KB" and
  "5 min ago" don't sort correctly as strings; Date Modified's own display
  text is ISO 8601 (`yyyy-MM-dd HH:mm:ss`) so it would actually sort
  correctly as plain text too, but uses the same subclass for consistency.
  Local Modified/Last Commit start blank and are filled in per-row by
  `_on_folder_author_ready` (see `FileRowAuthorsWorker` below) via
  `_row_for_path` — since the table is fully rebuilt on every navigation,
  revisiting a folder briefly shows these two columns blank again until
  the async worker (usually near-instant, since "Last Commit" is cached by
  relative path) re-populates them. `search_edit`'s filtering
  (`_apply_search`) hides non-matching rows directly via
  `setRowHidden` instead of a proxy-model filter, and is re-applied at the
  end of every `_populate_table` call so a folder switch doesn't silently
  drop the current search text's effect.
  `search_edit` sits at the end of the same nav row as the breadcrumb path
  field (`lineEdit_path`) rather than on its own row below the table. Each
  Folder Navigator column list uses zero item padding/margin (on top of
  `setSpacing(0)`) to keep entries as compact as possible. A "Last Opened
  File"/"Bookmarks" side panel (`tableWidget_last_opened_file`/
  `tableWidget_bookmarks`, defined in `explorer_section.ui` — plain
  `QTableWidget`s, headers hidden via code in `_setup_last_opened_table`/
  `_setup_bookmarks_table`, not `.ui` attributes; migrated from
  `QListWidget`/`QListView` so both could grow an icon column) sits to the
  left of the Folder Navigator. Column 0 on both is icon-only (file or
  folder glyph via `_file_icon()`, `QFileIconProvider` rather than a
  bundled bitmap since a bookmark can point at either), fixed at 24px; Last
  Opened has a 3rd column, on-disk mtime formatted by `file_table_proxy.py`'s
  `format_time_ago()` (`_mtime_ago()`). Every row's path lives in
  `Qt.UserRole` on the column-0 item specifically (not duplicated across
  the row) — click handlers look it up via
  `table.item(clicked_item.row(), 0).data(Qt.UserRole)`. Last Opened is an
  MRU list (capped at
  `_MAX_LAST_OPENED`) appended to whenever a table double-click actually
  opens a file (`_record_last_opened`, called from
  `_on_table_double_clicked`), backed by `LastOpenedStore`
  (`last_opened_store.py`, see below) rather than kept purely in-memory —
  rebuilt from that store on every `set_root()`/repo switch, so it
  survives app restarts. Clicking an entry (`_on_last_opened_clicked`)
  navigates to that file's current parent folder and then selects the
  file's own row in the table (`_select_file_in_table`, via
  `_row_for_path`) — deliberately no
  double-click-to-open wired up here, so this list can never be a second
  way to launch a file, only a navigation-plus-highlight shortcut back to
  one. `open_directory_button` (`pushButton_open_current_directory`, in the
  nav row) opens `_current_path` in the OS file explorer via
  `core/os_utils.py`'s `open_in_file_explorer`.
  `absolute_relative_switch` (`pushButton_absolute_relative_switch`, in the
  nav row next to the breadcrumb) toggles `_path_mode`
  (`"absolute"`/`"relative"`, **defaults to `"relative"`** — set in
  `RepoBrowserWidget.__init__` and mirrored in the `.ui`'s default button
  text so Designer's preview matches the runtime default) and re-renders
  the breadcrumb text (`_update_breadcrumb_text`) accordingly — the
  button's own label always names the *current* mode ("Absolute" while
  showing an absolute path, "Relative" while showing a repo-relative one),
  not the mode a click would switch to. Relative display
  (`_relative_display_str`) always starts with the repo's own folder name
  (`_root.name`) rather than being relative to `_root` itself (unlike the
  pre-existing `_relative_path_str`, used for git/commit-history lookups,
  which omits it) — e.g. `MyRepo/assets/model.ma`, per the "relative path
  always starts at the repo name" convention.
  Typing into the breadcrumb and pressing Enter (`_on_breadcrumb_entered`)
  auto-detects whether the typed text is absolute or relative
  (`Path(text).is_absolute()`) and resolves it via `_resolve_typed_path`,
  which rebases either form onto this machine's own `_root` by finding the
  repo folder name inside the typed path's parts and reattaching the
  remainder to `_root` — this is what lets a teammate's absolute path
  (different drive/machine, e.g. `D:/OtherUser/storage/MyRepo/assets`)
  still resolve locally instead of failing outright, since it shares the
  same repo-name-relative suffix. A typed path that doesn't contain the
  repo name anywhere is treated as absolute-or-nothing (used as a literal
  absolute path if it is one, otherwise rejected and the breadcrumb
  reverts to the current path). If the resolved path is a **file** rather
  than a folder, `_on_breadcrumb_entered` mirrors
  `_on_last_opened_clicked`'s behavior exactly — navigates to the file's
  parent folder (`_navigate_to`) and selects the file's own row
  (`_select_file_in_table`) rather than trying to "open" it; only a
  resolved folder navigates into itself. On successful navigation,
  `_set_path_mode` is called with the detected mode so the switch button
  and breadcrumb stay in sync with whatever the user typed.
- `bookmarks_store.py` — `BookmarksStore`: "Add this to bookmarks" (table
  row context menu) persists the clicked file/folder's repo-relative path
  via `MetadataStore.get_repo_plugin_data`/`set_repo_plugin_data`
  (`plugin_id="explorer"`, key `"bookmarks"`) — repo-scoped and
  cloud-synced through that repo's own project blob (see `plugin-api.md`'s
  config-stores table and `plugins-guide.md`'s "Sharing data with another
  plugin"), not a local `cache/` file like `LastOpenedStore`, since
  bookmarks are meant to show up for every artist on that repo.
  `RepoBrowserWidget` only constructs a store once `set_root()` has both a
  `MetadataStore` (`metadata_store` ctor param, from `api.metadata`) and a
  `project_id` — `RepoBrowserPage` now tracks `_active_project_id`
  (captured from `set_repo()`'s `project` arg) so `refresh_content()`'s
  internal `set_repo(None, ...)` fallback call still has a project id to
  pass through. `listView_bookmarks` is a plain `QListView` (not
  `QListWidget`) in the `.ui`, backed by a `QStandardItemModel` built in
  code (`bookmarks_model`) rather than `QListWidget` items — same
  repo-relative-path-in-`Qt.UserRole` convention as `last_opened_list`
  otherwise. Right-clicking an existing bookmark offers "Remove Bookmark".
  Bookmarks whose target doesn't exist on disk are filtered out of the
  *displayed* list by `get_bookmarks()`, but — unlike
  `LastOpenedStore.get_last_opened()`'s self-pruning — this is **not**
  persisted back to the store. `BookmarksStore` is the team-shared,
  cloud-synced blob (see above), so "missing on disk" on one machine often
  just means that machine hasn't pulled/cloned the file yet, not that the
  bookmark is actually gone; auto-saving the filtered list on every
  `get_bookmarks()` call (as it used to) would delete the bookmark for
  every other artist the next time anyone opened Explorer while behind on
  a pull. Real removal only happens through the explicit "Remove Bookmark"
  context-menu action (`remove()`).
- `last_opened_store.py` — `LastOpenedStore`: persists the Last Opened
  Files list to **this app's own**
  `<UkoreHub_root>/cache/explorer/last_opened_<repo_id>_<username>.json`
  — a **local, per-repo, per-OS-user** cache, not team/studio-shared data
  (never goes through `PluginConfigStore`/`api.plugin_config_store`).
  Stores repo-relative paths (survives a different drive letter machine to
  machine), scoped by both the repo's id and OS username (`getpass.getuser()`,
  sanitized to a safe filename). Used to live inside the browsed repo's own
  folder instead (same convention `cache/plugins/`-clone browser tools once
  used) but that put the file at the mercy of *that* repo's own
  `.gitignore` — several studio repos didn't exclude it, so this list kept
  getting committed to their history. `cache/` is this app's own repo,
  already wholesale gitignored (same directory `cache/plugins/` repo
  plugins live under), so this sidesteps the problem entirely rather than
  depending on every browsed repo's `.gitignore` being correct.
  `get_last_opened()` also prunes (and persists the removal of) any entry
  whose file no longer exists on disk, so deleted files don't linger in
  the list forever.
- `path_commit_history_panel.py` — `PathCommitHistoryPanel`: commit history
  for whichever **file** is currently selected in the file table — narrower
  than the whole-repo log on `plugins/core/submit/repo_git_status_page.py`.
  Only ever populated for an actual file selection (`clear()` empties the
  table — `setRowCount(0)`, no hint-text row — on folder navigation, a
  directory selection, or no selection at all — see
  `RepoBrowserWidget._on_table_selection_changed`/
  `_clear_file_panels`; this used to also fire once per folder navigated
  into, which was both the wrong UX and a real perf/crash risk under rapid
  double-click, see below). A plain controller class (not a `QWidget`) that
  renders into `tableWidget_file_commit_history`, a `QTableWidget` authored
  directly in `explorer_section.ui` (Author/Message/Time columns, header
  hidden) — it used to own its own scrollable `CommitCard`-based widget
  tree inserted into `groupBox_5` at runtime; migrated so the layout can be
  edited in Designer instead. Still shares `CommitHistoryEntry`/
  `format_commit_date`/`fetch_entries_via_github` with Submit via
  `interface/shared/commit_history.py` (that shared helper module stays in
  `interface/`, imported normally by both plugins) — just not `CommitCard`
  anymore. `_start_fetch`'s `_retire_worker` keeps a strong reference to any
  `PathCommitHistoryWorker` being replaced (in `self._retiring_workers`)
  until its own `finished` signal fires, instead of letting Python's
  refcounting drop the last reference to a `QThread` the instant a queued
  request re-triggers `_start_fetch` — `entries_ready` is emitted as the
  last line of `run()`, so the OS thread may not have fully unwound yet;
  destroying a `QThread` before that is a real, documented Qt crash ("QThread:
  Destroyed while thread is still running") that gets more likely the
  faster the user navigates/selects.
- `file_local_change_panel.py` — `FileLocalChangePanel`: whether the
  currently-selected file has an uncommitted local change (working tree
  modification/untracked/staged, via `GitService.get_status(repo_path)`).
  Same shape as `PathCommitHistoryPanel` — plain controller class over
  `tableWidget_file_local_change` (Author/Time columns, header hidden),
  same `clear()`-on-non-file-selection contract, same
  `_retire_worker`/`_retiring_workers` `QThread`-lifetime pattern. "Author"
  is `local_config_store.github_username` (there's no commit yet to read an
  author from — it's always the signed-in user), read fresh on every result
  rather than cached at construction so a login/logout mid-session shows up
  next selection; "Time" is the file's on-disk mtime (`Path.stat()`, not
  `QFileSystemModel`), formatted via `file_table_proxy.py`'s
  `format_time_ago`. `RepoBrowserWidget` now takes an optional
  `local_config_store` param (threaded through from `RepoBrowserPage`,
  which already had one) just to construct this.
- `file_local_change_worker.py` — `QThread` backing
  `file_local_change_panel.py`'s `git status --porcelain` lookup (via
  `GitService.get_status`) + file-mtime stat, off the UI thread. Not
  cached across selections (unlike commit history) — a working-tree status
  can change the moment the user saves the file in another app, so always
  refetches on `show_local_change_for`.
- `file_table_proxy.py` — just `format_time_ago(dt)` now ("5 min ago"/"2
  hours ago"/etc., shared by `browser_widget.py` and
  `file_local_change_panel.py`). Used to also hold `FileTableFilterProxy`,
  a `QSortFilterProxyModel` that wrapped a `QFileSystemModel` and appended
  synthetic columns for Time Ago/Local Modified By/Last Commit By — removed
  when the file table (see above) moved from a model/view
  `QTableView`+`QFileSystemModel` to a plain `QTableWidget` populated
  directly from `iterdir()`/`stat()`, which has no source model to proxy
  in the first place.
- `file_row_authors_worker.py` — `FileAuthorInfo` (dataclass:
  `local_modified_by`/`local_modified_icon`/`last_commit_by`/
  `last_commit_icon`) + `FileRowAuthorsWorker`: `QThread` that, for every
  entry (file or folder) in the folder `RepoBrowserWidget._apply_settled_navigation`
  just landed on, resolves both new columns and emits one `entry_ready`
  signal per entry as it resolves. "Local Modified By" is one
  `GitService.get_status(repo_path)` call for the whole folder (cheap),
  reused for every entry — matching path means the signed-in user
  (`local_config_store.github_username`), since an uncommitted change has
  no commit author; folders never get one (only files can appear in
  `unstaged_changes`/`staged_changes`). "Last Commit By" is
  GitHub-API-first/local-git-fallback per entry (`fetch_entries_via_github`
  then `GitService.get_commit_log_for_path`, same pattern as
  `PathCommitHistoryWorker`) — the expensive part, so it's cached in
  `RepoBrowserWidget._last_commit_cache` (keyed by relative_path, shared
  across every `FileRowAuthorsWorker` instance for the repo's lifetime —
  reset only on `set_root()`/repo switch) and never re-fetched for a path
  already resolved, unlike Local Modified By which is always recomputed
  fresh. The cache dict is safe to mutate directly from `run()` (background
  thread) for the same reason `PathCommitHistoryPanel`'s `avatar_cache` is:
  only one worker is ever active at a time
  (`RepoBrowserWidget._retire_authors_worker` retires the previous one
  before a new one starts) and the GUI thread never touches it directly,
  only the per-entry results delivered via the signal. `run()` checks
  `isInterruptionRequested()` between entries (set by `requestInterruption()`
  in `_retire_authors_worker`) so navigating away mid-fetch stops promptly
  instead of grinding through the rest of the old folder's files first —
  same `_retiring_authors_workers`-holds-a-strong-reference-until-`finished`
  pattern as `PathCommitHistoryPanel._retire_worker`, for the same
  QThread-lifetime reason.
- `path_commit_history_worker.py` — `QThread` backing
  `path_commit_history_panel.py`'s GitHub-API-first/local-git-fallback
  fetch, off the UI thread.
- **Navigation debounce + selection-index hygiene**: `_navigate_to` starts a
  120ms single-shot `_nav_settle_timer` instead of immediately re-running
  Miller-column population (`_sync_columns_from_path`, several synchronous
  `iterdir()`+`sorted()` disk scans) — double-clicking through several
  folders quickly used to redo that scan (and, before the change above, a
  git-log fetch) on every single click along the way; now only the folder
  the user actually lands on pays for it (`_apply_settled_navigation`).
  `_navigate_to` also calls `_clear_file_panels()` right after repopulating
  the table — rebuilding the table's rows already drops any selection made
  in the previous folder, but the explicit call avoids depending on
  `currentRowChanged` firing synchronously for that. `_relative_path_str`
  (used for every git/GitHub
  lookup keyed by path) returns `.as_posix()`, not `str(path)` — a
  Windows-style backslash-separated relative path silently fails to match
  either `git log -- <path>`'s pathspec or the GitHub commits API's `path=`
  query parameter.

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive, an `interface/shared/` addition, or touches
`interface/main_window.py`'s generic `UICommandService` wiring.
