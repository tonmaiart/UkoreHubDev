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
  `lineEdit_column_1..5_search`, `tableView_current_directory`,
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
  `navigate_and_focus`, not by importing this module directly. Also
  implements the optional `refresh_content()` protocol method
  (`interface/page_protocols.py`'s `RefreshablePage`, called via
  `UICommandService.refresh_section("repo_browser")`) — Submit's "Sync
  Others Commit" button calls into this after every sync so the file table
  doesn't sit stale until the user manually reopens the tab or restarts the
  app (`QFileSystemModel`'s own filesystem watcher can miss/lag a bulk
  change like a git clone/pull). `refresh_content()` re-runs the same
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
  semantics, so don't conflate them. Both use built-in Qt icons via
  `_apply_nav_icon` (`QStyle.SP_ArrowBack` / `QStyle.SP_FileDialogToParent`
  — migrated 2026-08-13 from 3 bundled-PNG path constants that pointed at
  files which never actually existed in the repo, so this had always
  silently fallen back to text-only buttons before; see `interface.md`'s
  Zero QSS Policy section). `add_folder_button` sits right after
  `up_button` in the nav row (`QStyle.SP_FileDialogNewFolder`, same
  `_apply_nav_icon` helper) and just calls
  `_create_new_folder(self._current_path)` — a toolbar shortcut for the
  same "Create New Folder" action described below.
  A Reload button (`reload_button`, `QStyle.SP_BrowserReload`, same
  `_apply_nav_icon` helper) sits right after `add_folder_button` in
  `nav_row` — calls `reload()`, which force-rescans the current folder from
  disk without changing which folder is open or touching navigation
  history. `QFileSystemModel` has no public "rescan" call and normally
  relies on its own filesystem watcher, which can miss or lag a bulk change
  like a git clone/pull (many files created/modified/deleted at once);
  `reload()` works around this by toggling `fs_model.setRootPath("")` then
  back to the real root, which forces Qt to drop its cached listing and
  re-fetch. `RepoBrowserPage.refresh_content()` (above) calls this same
  method for the automatic post-sync case — the nav button is the manual
  escape hatch for any other staleness (e.g. a file changed by an external
  tool while Explorer was open).
  Right-clicking a row opens a context menu (Add this to bookmarks/Copy
  Name/Copy File Path/Rename/Delete) via `_on_table_context_menu`;
  right-clicking blank space in the table (no row under the cursor) falls
  through to `_on_empty_area_context_menu` instead, whose Create New
  Folder/Rename Folder/Delete Folder act on the currently open folder
  (`_current_path`) rather than a selected row — Rename/Delete Folder are
  disabled while `_current_path` is the repo root, since renaming/deleting
  it out from under `set_root()`'s `fs_model`/`_last_opened_store` would
  leave them pointed at a path that no longer exists. The file table hides
  the Type column (redundant with
  the file's icon/name) and gives Name/Date Modified `Stretch` resize
  priority over Size and the synthetic Time Ago column (see
  `file_table_proxy.py` below) so they can't get squeezed narrow.
  `search_edit` sits at the end of the same nav row as the breadcrumb path
  field (`lineEdit_path`) rather than on its own row below the table. Each
  Folder Navigator column list uses zero item padding/margin (on top of
  `setSpacing(0)`) to keep entries as compact as possible. A "Last Opened
  File"/"Bookmarks" side panel (`listWidget_last_opened_file`/
  `listView_bookmarks`, defined in `explorer_section.ui`) sits to the left
  of the Folder Navigator. Last Opened is an MRU list (capped at
  `_MAX_LAST_OPENED`) appended to whenever a table double-click actually
  opens a file (`_record_last_opened`, called from
  `_on_table_double_clicked`), backed by `LastOpenedStore`
  (`last_opened_store.py`, see below) rather than kept purely in-memory —
  rebuilt from that store on every `set_root()`/repo switch, so it
  survives app restarts. Clicking an entry (`_on_last_opened_clicked`)
  navigates to that file's current parent folder and then selects the
  file's own row in the table (`_select_file_in_table`, via
  `fs_model.index()`/`proxy.mapFromSource()`) — deliberately no
  double-click-to-open wired up here, so this list can never be a second
  way to launch a file, only a navigation-plus-highlight shortcut back to
  one. `open_directory_button` (`pushButton_open_current_directory`, in the
  nav row) opens `_current_path` in the OS file explorer via
  `core/os_utils.py`'s `open_in_file_explorer`.
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
  Bookmarks whose target no longer exists on disk are dropped (and the
  store re-saved) the next time `get_bookmarks()` runs, same self-pruning
  behavior as `LastOpenedStore.get_last_opened()`.
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
- `path_commit_history_panel.py` — `PathCommitHistoryPanel`: commit
  history scoped to whichever path is currently being viewed — narrower
  than the whole-repo log on `plugins/core/submit/repo_git_status_page.py`.
  Shares `CommitCard`/`CommitHistoryEntry` with Submit via
  `interface/shared/commit_history.py` (that shared helper module stays in
  `interface/`, imported normally by both plugins).
- `file_table_proxy.py` — `FileTableFilterProxy`: the `QSortFilterProxyModel`
  behind the file table (search-text filtering) that also appends a
  synthetic "Time Ago" column (`TIME_AGO_COLUMN = 4`, after
  `QFileSystemModel`'s real Name/Size/Type/Date Modified columns 0-3) —
  `format_time_ago()` renders `QFileSystemModel.lastModified()` as "5 min
  ago"/"2 hours ago"/etc. `QSortFilterProxyModel`'s default
  `index()`/`mapToSource()` bound column requests against the *source*
  model's own `columnCount()`, so a column that doesn't exist there (index
  4 vs. `QFileSystemModel`'s 4 real columns, 0-3) needs `index()` and
  `mapToSource()` overridden to redirect it onto column 0's source index
  instead — every column of the same row shares one internalPointer/parent
  in Qt's model/view contract, so reusing column 0's identifies the same
  file correctly (this is also why existing code like
  `proxy.mapToSource(current)` in `_on_table_selection_changed`/
  `_on_table_double_clicked` keeps working even if the user clicks/double-
  clicks the Time Ago cell itself). Clicking the Time Ago column header is
  a no-op (`sort()` override) rather than sorting — there's no real source
  column to sort by, and reconstructing one inside `lessThan()` isn't worth
  the complexity for what's a supplementary display column.
- `path_commit_history_worker.py` — `QThread` backing
  `path_commit_history_panel.py`'s GitHub-API-first/local-git-fallback
  fetch, off the UI thread.

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive, an `interface/shared/` addition, or touches
`interface/main_window.py`'s generic `UICommandService` wiring.
