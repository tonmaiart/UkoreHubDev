# plugins/core/ExternalPluginManager/

Moved here (2026-08-13) from `app/plugins/core/ExternalPlugins/README.md`,
folder/tab renamed from "ExternalPlugins"/"External Plugins" to
"ExternalPluginManager"/"External Plugin Manager" (2026-08-13) to
disambiguate the manager plugin itself from the `cache/plugins/` entries
("external plugins") it manages — its manifest `id` and storage key stay
`external_plugins` (unchanged, for per-project catalog data compatibility).
See `plugins-guide.md` for the general plugin-authoring conventions this
plugin follows, and `core-api.md` for `core/`'s structure.

Settings > Project > "External Plugin Manager" — the active Project's own
catalog of `cache/plugins/` repo plugins (each its own separate git
clone, see `plugins-guide.md`), whether already cloned or not, with
Clone/Pull and an ahead/behind check against each one's remote. Built
because there's no auto-fetch/clone mechanism anywhere else — every
`cache/plugins/` entry today was cloned by hand. A background auto-sync
engine (see "Auto-sync engine" below) now handles the common case of that
by itself — this page's manual actions remain for everything the engine
can't or shouldn't do alone (first-ever clone of a brand new catalog
entry, resolving a conflict).

As of 2026-08-11 the catalog itself is per-project, not studio-wide — see
"Per-project catalog, not a studio-wide file" below. Existing entries in
the old shared `data/plugins/core/external_plugins.json` were **not**
migrated (an explicit choice, not an oversight — every project starts
with an empty catalog and each entry has to be re-added per project it's
actually used in); that old file is left on disk, unread by anything now.

- `manifest.json` — plugin id `external_plugins`.
- `catalog_store.py` — `CatalogEntry` (`id, name, git_url, folder_name,
  plugin_id`) + `ExternalPluginCatalog`, a thin wrapper around a
  `ProjectPluginConfigStore` (`core/extensibility/config_store.py`) —
  i.e. the active Project's own
  `Project.plugin_data["external_plugins"]["catalog"]`
  (`core/models.py`), synced the same way the rest of that project's data
  is (`MetadataStore`'s per-project cloud sync, see the
  `ukorehub-cloud-sync` skill) — `list_entries()/add_entry()/edit_entry()/
  delete_entry()/update_plugin_id()`. `config_store` is `None` when no
  project is active yet; every method degrades to a no-op/empty list
  rather than crashing. `folder_name` must be a single safe path segment:
  it's used directly as `cache/plugins/<folder_name>`. `plugin_id` is a
  cache of "what `PluginManifest.id` does this entry produce once cloned",
  unknown until some machine's auto-sync engine or the Requirements &
  Plugins manual clone-on-check flow backfills it — see "Auto-sync engine"
  below for why this exists.
- `catalog_entry_dialog.py` — `CatalogEntryDialog`: Git URL / Name /
  Folder Name fields for Add/Edit, same shape as `interface/settings/
  program_dialog.py`'s `ProgramDialog`. Name and Folder Name auto-fill
  from the Git URL (`core/vcs/paths.py`'s `extract_git_repo_name`) the
  moment a URL is typed, as long as the user hasn't already typed
  something into that field themselves — so adding an entry is usually
  just pasting a Git URL. Never exposes `plugin_id` — it's derived/cached,
  not something a human sets.
- `sync_engine.py` — Qt-free sync logic: `resolve_required_entries()`
  (which catalog entries the active repo's `Repo.required_plugin_ids`
  resolves to, via each entry's `plugin_id`) and `sync_entry()`
  (clone-if-missing / pull-if-present / conflict-check for one entry).
- `sync_worker.py` — `ExternalPluginSyncWorker(QThread)`: runs
  `sync_engine` for a batch of entries sequentially, off the UI thread,
  emitting `entry_synced`/`backfill_ready` signals rather than writing
  anywhere directly.
- `sync_status_store.py` — `ExternalPluginSyncStatusStore`: per-machine
  (`shared=False`) record of the sync engine's last conflict/error result
  per entry, so it survives until someone opens this tab.
- `last_check_store.py` — `LastCheckedStore`/`LastCheckResult`: per-machine
  (`shared=False`) record of the *last manual "Check for Status" result*
  per entry (status bucket + detail + `checked_at`), in its own top-level
  JSON key (`last_check_result`) separate from `sync_status_store.py`'s
  `sync_status` key — kept separate specifically so the auto-sync engine's
  own set/clear calls on `sync_status` (see "Auto-sync engine" below) can
  never wipe out a manual check's cached result. This is what lets
  `_local_status` (below) keep showing e.g. "3 commits behind" after the
  Settings dialog is closed and reopened, instead of reverting to a bare
  "Up to date" until the next explicit check.
## Two pages, two windows (split 2026-08-24)

This plugin used to be one Settings tab with every action (Add/Edit/Remove
*and* Clone/Unclone/Pull/Force Update/Check for Status/Open Directory/Bulk
Push) crammed into one `.ui`/page. It's now split into a backend admin
page (Settings > Project, rarely opened) and a day-to-day operational page
(Settings > Account, key `external_plugins_updater`, label "Plugins") —
same catalog, same stores, two different windows, Python classes, and
Settings categories:

- **`ExternalPluginManagerWindow.ui` / `external_plugins_page.py`
  (`ExternalPluginsPage`)** — Settings > Project tab (`register_settings_tab`,
  `CATEGORY_PROJECT`, key `external_plugins`, unchanged). Pure catalog CRUD:
  Add / Edit / Remove a `CatalogEntry` (name, Git URL, folder name). Table
  has 4 columns (Name, **Requires**, Git URL, Folder Name) — no Status/
  Detail/Last Checked (that's the Updater page's job), but this page does
  take `plugin_catalog` (the already-discovered `DiscoveredPlugin` list)
  specifically to resolve and show each entry's own `_requires_label`
  (same logic as the Updater page used to have — an entry that isn't
  cloned yet shows no requires text, since there's no manifest.json to
  read until it is). No `git_service`/`plugins_root`/`sync_status_store`/
  `last_check_store` dependency though — this page still never touches
  live git state. Widget object names: `tableWidget_external_plugin_repo`,
  `pushButton_add_repo`/`_edit_repo`/`_remove_repo`. Single-row selection
  (`QAbstractItemView.SingleSelection`) since Edit/Remove are the only
  row-scoped actions left.
- **`ExternalPluginUpdaterWindow.ui` / `external_plugin_updater_page.py`
  (`ExternalPluginUpdaterPage`)** — a Settings tab (`register_settings_tab`,
  key `external_plugins_updater`, label **"Plugins"**, order 10,
  `category=CATEGORY_GENERAL`) — Settings > **Account**, alongside the
  built-in "Account" tab (`common_settings_page.py`, see `interface.md`).
  Went through two other placements before landing here (2026-08-24): first
  its own top-level sidebar section, then briefly a `standard_icon` was
  picked for that section (`QStyle.SP_VistaShield`) before the section
  approach itself was dropped in favor of Settings > Account — neither the
  icon nor `SectionSpec` registration apply anymore, since
  `SettingsTabSpec` has no icon parameter. 4-column table (Name, Status,
  Detail, Last Checked — **no Requires column here**, deliberately, since
  that's static catalog metadata the Manager page already shows and this
  page is about live git status instead) with the same `_local_status`/
  status-bucket/icon logic the old single page had. Still takes
  `plugin_catalog` too, but only to tell "cloned but not discovered by
  this session yet" apart from a real up-to-date row (`_local_status`'s
  `_PENDING_RESTART_DETAIL` branch) — not to render a Requires column.
  Widget object names: `tableWidget_external_plugin_repo`,
  `pushButton_check_for_status`, `pushButton_update_all`.

Both pages share the same `ExternalPluginCatalog`/`ExternalPluginSyncStatusStore`/
`LastCheckedStore` instances (built once in `plugin.py`'s `_SyncController`,
see below) — an edit made in the Manager tab is visible in the Updater tab
immediately, no caching or refresh coordination needed between them.

**Status column** (Updater page only) is one of exactly 5 canonical
buckets, each with its own `QStyle` standard icon: `Error`
(`SP_MessageBoxWarning`), `Not Clone` (`SP_TitleBarMaxButton`), `Modified`
(`SP_MessageBoxInformation`), `Update Needed` (`SP_ArrowDown`), `Up to
date` (`SP_DialogApplyButton`). Everything more specific — ahead/behind
counts, conflict-resolution instructions, broken-git instructions,
auto-sync failure text, "no upstream configured" — goes in the **Detail**
column instead of being its own bucket. `_local_status` (fast, local-only,
used by every `refresh_list()`) checks live git state first — `is_cloned`
→ `is_repo_root` → `has_unresolved_merge` → working-tree dirty — and only
ever falls back to `sync_status_store`'s persisted result *within the
branch it applies to* (never as a blanket first check — a stale persisted
error can never override real, current, local git state). When none of
the local checks find anything wrong, it reads `last_check_store` for the
last Check for Status result instead of guessing — an entry that's never
been checked shows `Up to date` with an empty Detail and a "Never" Last
Checked column, rather than a distinct 6th status.

### Updater page toolbar: Check for Status (parallel) / Update All

- **"Check for Status"** (`_on_check_for_status`) now checks every row
  **in parallel** instead of one at a time — no selection, always every
  row. Each cloned+valid row's fetch/ahead-behind/working-tree check runs
  as its own `_StatusCheckTask` (`QRunnable`) on a dedicated
  `QThreadPool` (`_MAX_PARALLEL_CHECKS = 8`), since every catalog entry
  lives in its own `cache/plugins/<folder>` clone — no two tasks in the
  same run ever touch the same folder, so there's nothing to race. Each
  task only ever emits through `_StatusCheckSignals` (a `QObject` owned by
  the page on the main thread) — Qt auto-queues that emit onto the main
  thread, so `_on_status_check_result` (which writes rows, the table, and
  `last_check_store`) never runs off the UI thread and needs no locking,
  same "workers only emit, controller writes" shape `sync_worker.py`
  already used for the (sequential) auto-sync engine. Not-cloned/broken-git/
  merge-conflict rows are resolved locally first (no thread dispatched for
  them) and shown immediately; only rows that need a real network call get
  a `_StatusCheckTask`. `safe_untrack_and_clean_ignored` still runs first
  per row (local untrack + commit only, never pushes) same as before the
  split. The button (and "Update All") disables itself for the whole run
  (`self._busy`) so a second Check/Update can't start mid-run and race a
  task still touching the same folder.
- **"Update All"** (`_on_update_all`) replaced "Update Selected"/"Force
  Update Selected" — one button, always force-updates **every** catalog
  entry, no selection needed, one `confirm_action` prompt up front (it's
  destructive — discards local changes/unpushed commits). Per entry: not
  cloned → Clone; cloned but `is_repo_root()` False (broken/interrupted
  clone) → delete the folder and Clone fresh; otherwise →
  `GitService.force_sync` (`core/vcs/git_service.py`) — `fetch` + `git
  reset --hard origin/<branch>` + `git clean -fd`, discarding every local
  change/unpushed commit and clearing any in-progress merge. Runs
  sequentially on the UI thread (like the old "Force Update Selected"
  did) — see "Why no background thread" below for why this one action
  deliberately isn't parallelized like Check for Status is. Clears
  `sync_status_store`/`last_check_store` for every entry it touches.

### Updater page: right-click context menu (Clone / Unclone / Open Directory / Bulk Push)

These four used to be their own toolbar buttons, each gated on exactly one
selected row (`_selected_row()`). They're now a `QMenu` built fresh on
`tableWidget_external_plugin_repo`'s `customContextMenuRequested`
(`_on_context_menu`) — right-clicking a row selects it and shows a menu
with each action enabled/disabled for that specific row's state exactly
the same way the old buttons were (`Clone` only if not cloned; `Unclone`/
`Open Directory` only if cloned; `Bulk Push` only if Status is `Modified`).
The menu is suppressed entirely while `self._busy` (a Check for
Status/Update All run in progress).

- **Clone** (`_on_clone`) — `GitService.clone`, then clears
  `sync_status_store` for that entry on success (closes the same
  stale-error gap a successful Pull/auto-clone already closed).
- **Unclone** — deletes the selected entry's local clone from disk (plain
  `shutil.rmtree`, confirmed first, the same OSError-message pattern as
  `interface/repo_settings/local_repository_page.py`'s "Remove Local
  Repositories"). The catalog entry itself stays, so it shows `Not Clone`
  afterward and can be Cloned again.
- **Open Directory** — opens the row's local clone in the OS file
  explorer via `core/os_utils.py`'s `open_in_file_explorer`; also how a
  dev reaches an `Error`-bucketed conflict row to resolve it, since this
  page builds no in-app conflict-resolution UI of its own.
- **Bulk Push** (`_on_stage_untracked_and_push`) — only reachable when the
  row's Status is `Modified`, which covers both working-tree changes *and*
  commits already made locally but not yet pushed (see `_format_status`'s
  "N commit(s) ahead — not pushed" branch). Stages every untracked/modified
  file (`GitService.stage_paths`) and commits with a message typed into a
  plain `QInputDialog` prompt only when there's actually something in the
  working tree to stage; when the entry is `Modified` purely from unpushed
  local commits (empty working tree), it skips staging/commit entirely and
  just pushes. On success it calls `last_check_store.clear(entry.id)`
  before `refresh_list()` recomputes the row — otherwise a stale cached
  "N commit(s) ahead" result from an earlier Check for Status would keep
  showing `Modified` even though the push that just ran already resolved
  it.
- `plugin.py` — `register(api)`: registers both the Settings tab
  (`ExternalPluginsPage`, CRUD-only) and the top-level section
  (`ExternalPluginUpdaterPage`), each building a fresh page per
  `page_factory` call — same "no long-lived page" convention every
  Settings tab/section uses (see `interface.md`'s `settings_view.py`
  entry). Also builds `_SyncController` once per app session — see
  "Auto-sync engine" below — which is the one long-lived thing in this
  plugin; its `ExternalPluginCatalog` is built once too
  (`api.project_plugin_config_store(PLUGIN_ID)`), safe to hold for the
  whole session because the active project never changes mid-session
  (switching projects means a full app restart — see `core_api`'s
  `LocalConfigStore.set_active_project`). Both pages read/write through
  this one shared `sync_controller.catalog`/`.status_store`/
  `.last_check_store` — no separate instance per page.

## Registration status (load/register, not sync)

Distinct from the auto-sync engine below (which reports *git* status —
clone/pull/conflict), `launcher.py`'s plugin discovery/apply loop
(`core/extensibility/loader.py`'s `discover_plugins`/`apply_plugins`,
called once at startup, before any plugin's `register(api)` runs — see
`plugins-guide.md`) now reports each plugin's **load/register** result via
the stdlib `logging` module (2026-08-21) instead of a bare `print`. A
`"repo"` (`cache/plugins/`, i.e. an "external plugin" in this app's own
vocabulary) plugin's result — success or failure, including *why* it
failed (no `manifest.json`, malformed manifest, `api_version` mismatch,
missing `entry_point`, an import-time exception, or `register(api)`
itself raising — see `core/extensibility/loader.py`'s `_load_one`/
`apply_plugins`) — logs through `logging.getLogger("ExternalPluginManager")`,
the same logger name this plugin's own `plugin.py` already uses for sync
status, so both show up together under one DebugConsole source. A bundled
`"core"` plugin's result logs through a separate `logging.getLogger("PluginLoader")`
instead, since core plugins are far less likely to break and don't belong
mixed into this plugin's own source. See
`developer/app/docs/plugins/DebugConsole.md` for how to view these live.

## Auto-sync engine

A repo's required `cache/plugins/` entries clone themselves and check for
updates automatically at app start and on every repo switch, instead of
waiting for someone to open this tab and click Clone/Pull by hand.
`plugin.py`'s `register(api)` subscribes `_SyncController.on_lifecycle_event`
to both `api.on_app_start`/`api.on_repo_changed` (`plugin_api/plugin_api.py`,
fired from `interface/main_window.py`'s `_start_app`/`_set_active_repo`) —
this is the entire lifecycle wiring; nothing outside this plugin folder
needed to change (beyond re-exporting `relaunch_ukorehub_exe` through
`plugin_api`, see below).

**Never auto-pulls — prompts Force Update/Ignore instead** (added
2026-08-20): an entry not yet cloned still clones itself silently (nothing
local to lose). But an already-cloned entry that's behind its remote
(`sync_engine.sync_entry` fetches + `get_ahead_behind`s it,
`STATUS_UPDATE_NEEDED`) is never pulled automatically anymore, regardless
of whether its working tree is clean or modified — `discover_plugins()`/
`apply_plugins()` only run once at startup, so a silent pull wouldn't take
effect until a restart anyway, and pulling into a dirty working tree risks
a conflict nobody asked for. Instead, once a whole sync run (and any run
it chained into via `_pending_context`, see the class docstring) settles,
`_SyncController._on_finished` shows one `QMessageBox` popup listing every
entry found behind, with two buttons:
- **"Force update and restart UkoreHub"** — `_force_update_and_restart`
  runs the same escape hatch as this tab's own "Force Update Selected" on
  every listed entry (not cloned/broken `.git` -> delete + Clone,
  otherwise -> `GitService.force_sync`, discarding local
  changes/unpushed commits), clears both stores for each, then
  unconditionally restarts (`_restart_app` — `relaunch_ukorehub_exe(api.app_root)`,
  falling back to `subprocess.Popen([sys.executable, *sys.argv])` for a
  dev-checkout run, then `QApplication.quit()` — the same fallback
  `interface/main_window.py`'s own `_restart_app` uses) even if some
  entries failed, since a partial success still needs the restart to load.
- **"Ignore"** — does nothing; the entry stays flagged `Update Needed` in
  `last_check_store` (so the Status column already reflects it without a
  manual Check for Status) and gets re-detected, not re-prompted again
  until the next app start/repo switch's own run finds it still behind.

`relaunch_ukorehub_exe` (`core/relaunch.py`) wasn't re-exported through
`plugin_api` before this — plugins couldn't restart the app at all. Added
to `app/plugin_api/__init__.py`'s re-export list (sourced from `core_api`,
which already had it) specifically for this popup — see
`developer/app/docs/plugin-api.md`'s Misc helpers entry.

- **Resolving "required but never cloned here"**: `Repo.required_plugin_ids`
  stores a plugin's *manifest id*, only learned by reading `manifest.json`
  after a clone exists (see `interface/repo_settings/
  requirements_and_plugins_page.py`'s `_on_catalog_entry_checked`). A
  machine that's never cloned a given entry has no other way to map a
  required manifest id back to that entry's `git_url`/`folder_name` — so
  `CatalogEntry.plugin_id` caches that mapping, backfilled the first time
  `sync_engine.resolve_required_entries()` sees the entry already
  discovered this session (matched by `folder_name`, via the same
  `plugin_catalog` `loader.discover_plugins()` already produced at
  startup — no extra manifest.json parsing) and written back through the
  shared catalog store, so once any one machine backfills it, every other
  machine's next catalog pull can resolve it too. A required manifest id
  with no `plugin_id` mapping anywhere yet just doesn't auto-clone until
  some machine backfills it (e.g. via the existing manual checkbox flow) —
  degrades gracefully, never crashes.
- **Runs on a background thread, not this page's synchronous pattern**:
  see "Why no background thread" below — that section is about this
  page's own deliberate, one-at-a-time button clicks, which is a different
  situation from an automatic sync firing on every app start and repo
  switch. `ExternalPluginSyncWorker` (`sync_worker.py`) is a real `QThread`,
  modeled on `plugins/core/submit`'s worker classes and
  `plugins/core/project_editor/required_repo_clone_worker.py`'s "QThread
  wraps a sequential clone/pull batch" shape. It only ever emits signals —
  `_SyncController` (in `plugin.py`) is the only thing that writes to the
  catalog (`update_plugin_id`) or the status store, and always on the main
  thread (Qt queues a cross-thread signal onto the receiving object's own
  thread automatically), so there's no locking anywhere in this engine.
- **Never overlaps two syncs on the same folder**: `_SyncController` runs
  at most one `ExternalPluginSyncWorker` at a time. A trigger that arrives
  mid-run replaces `_pending_context` (keeping only the latest) instead of
  starting a second worker; the in-flight worker's `finished` signal starts
  exactly one more run for that latest context once it completes — so a
  rapid double repo-switch still eventually syncs the repo actually left
  active, without two `git pull`s ever racing on the same
  `cache/plugins/<folder>` clone.
- **Conflict detection reuses existing `GitService` primitives** —
  `has_unresolved_merge()` (checks `.git/MERGE_HEAD`) and the same
  `GitOperationError`-on-failure contract `pull()` already had. `sync_entry()`
  never force-pushes, aborts a merge, or discards anything: a conflict is
  left exactly as git leaves it, reported as `sync_engine.STATUS_CONFLICT`
  (surfaced by `external_plugins_page.py` as the `Error` status bucket, with
  the conflict message in the Detail column), and re-detected (not
  re-attempted) on every later sync until a dev resolves it by hand via
  "Open Git Directory".

## Per-project catalog, not a studio-wide file

`interface/repo_settings/requirements_and_plugins_page.py`'s External column
(Settings > Repo Setting (Dev) > Requirements & Plugins) lists every
`cache/plugins/` repo plugin `discover_plugins()` finds cloned on this
machine, plus every catalog entry the *active project* has that isn't
cloned/discovered yet (`RequirementsAndPluginsPage._read_external_catalog()`
reads `self.store.get_project_plugin_data(project_id, "external_plugins")`
directly — same `MetadataStore` instance this plugin's own
`ProjectPluginConfigStore` reads/writes through, so an edit made on the
External Plugins tab is visible here immediately, no caching on either
side).

Before 2026-08-11 this was one studio-wide catalog
(`data/plugins/core/external_plugins.json`, `shared=True`
`PluginConfigStore`) shown identically to every project, plus a same-day,
twice-reverted attempt at a per-project *selection filter* layered on top
of that one shared file (a "Used by this Project" checkbox, then an
auto-select-on-add version — see prior git history for the full story if
needed). Both filter attempts shared the same flaw: entries already in the
catalog before the filter existed had no way to gain a selection record,
so an existing project's External list could go silently empty even
though the shared catalog itself was full.

Moving the catalog itself into `Project.plugin_data` (this file's own
`ExternalPluginCatalog`, see above) removes that whole bug class rather
than fixing it a third time: there is no filter sitting on top of a shared
list anymore, so there's nothing for a pre-existing record to fail to
match against — each project's catalog **is** its own list, empty by
default. The cost is the flip side of the same design: nothing carries
over from the old shared file automatically. That old file
(`data/plugins/core/external_plugins.json`) is left on disk untouched but
unread — the 5 entries it had (`maya_launcher`, `UkoreReferenceEditor`,
`PublishApi`, `MayaToolkit`, `MayaFileBrowser`) need re-adding by hand to
whichever project(s) actually use them, an explicit choice made when this
migration shipped (2026-08-11), not an oversight.

A selected-but-not-yet-cloned entry doesn't require a separate trip to this
page to clone it: its row on Requirements & Plugins is itself checkable,
and checking it clones straight into `cache/plugins/<folder_name>`
immediately (no confirm prompt — the only git-clone action in the app that
skips one, since checking the box already is the explicit action), then
marks it required for that repo by reading the fresh clone's
`manifest.json` directly (no import/execution — just a `json.loads`, via
`RequirementsAndPluginsPage._read_manifest_if_cloned`). Since
`discover_plugins()`/`apply_plugins()` are one-shot at app startup, the
plugin still doesn't actually *load* until UkoreHub is restarted — the row
reflects that afterward as "(installed — restart UkoreHub to activate)"
rather than going back to "(not installed — ...)".

### Showing `PluginManifest.requires`

Each catalogued row's label also shows `— requires: X, Y` when the entry is
cloned and its `manifest.json` declares `requires` — resolved via
`PluginAPI.plugin_catalog` (the same `discover_plugins()` result the rest of
the app uses; threaded into this page's constructor by `plugin.py`), not by
this page re-parsing `manifest.json` itself. An entry that isn't cloned yet
shows no requires text — there's no manifest to read until it is. On
Requirements & Plugins, checking a plugin whose `requires` aren't all
enabled yet for that repo prompts to enable the closure too (see that
file's `_confirm_and_enable_requirements`) — there's no equivalent
cascade here, since this page has nothing per-repo or per-project left to
cascade into.

## Why `is_repo_root`, not just `is_cloned`

`GitService.is_cloned()` only checks that a `.git` entry exists — true
even for an empty/corrupt `.git` directory left by an interrupted clone,
in which case git's own repo-discovery silently walks up to whatever real
repository is further up the tree (in this app's case, UkoreHub's own
repo root) instead of failing. Update All/Check for Status/Bulk Push (all
on `external_plugin_updater_page.py`) all gate on `GitService.is_repo_root()`
instead of just `is_cloned()`, which actually confirms `git rev-parse
--show-toplevel` resolves back to the folder itself — see the
`ukorehub-core` skill; a broken `cache/plugins/AdvancedSkeleton/.git` once
almost caused "Bulk Push" (formerly "Stage Untracked & Push") to commit and
push UkoreHub's own uncommitted local changes into AdvancedSkeleton's
remote. A folder that
fails this check
shows `Broken .git directory (not a valid clone) — delete the folder and
Clone again` rather than being silently treated as a normal clone.

## Why no background thread (for the Manager page, and most of the Updater page)

Opening either page only does a fast local filesystem pass (cloned vs. not
cloned) — no network call. On the Updater page, Clone/Unclone/Open
Directory/Bulk Push (the context-menu actions) and Update All still call
git over the network but run synchronously on the UI thread (with
`QApplication.setOverrideCursor(Qt.WaitCursor)`), same as before the
split — each is still a single deliberate click (a context-menu action on
one row, or one confirmed "Update All"), not something worth threading on
its own. `SettingsTabSpec` (the Manager page's kind) has no
`background_threads` shutdown-cleanup hook, and `SettingsDialog` is
rebuilt fresh on every open, so the Manager page never needed real
threading in the first place — it doesn't call git at all anymore.

**"Check for Status" is the one exception** (see "Updater page toolbar"
above) — it now dispatches a `QRunnable` per row onto a `QThreadPool`
instead of looping synchronously with `processEvents()` the way the old
single page did. The difference from the other actions above isn't "this
one matters more" — it's that Check for Status is the one action that
routinely touches *every* row in the catalog in a single click (Update All
does too, but stays sequential since force-updating is destructive and
correctness matters more than speed there), so it's the one place a large
catalog's worth of sequential network round-trips would actually be felt.
If Update All or the context-menu actions ever need the same treatment,
`_StatusCheckTask`/`_StatusCheckSignals` is the pattern to reuse — the
requirement is the same one that already makes the parallel Check for
Status safe: every task must operate on a distinct
`cache/plugins/<folder>` clone, never two tasks on the same one.

The auto-sync engine (see "Auto-sync engine" above) is a different
situation from either page's own manual actions — it fires unattended on
every app start and repo switch and may need to touch several plugins
sequentially over the network without blocking app startup, so it
deliberately uses a real `QThread` (`sync_worker.py`) rather than either
page's own synchronous-click or per-row-`QThreadPool` pattern.
