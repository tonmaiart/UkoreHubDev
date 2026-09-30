# plugins/core/project_editor/

Moved here (2026-08-13) from `app/plugins/core/project_editor/README.md`.
See `plugins-guide.md` for the general plugin-authoring conventions this
plugin follows.

Repo list editor for the Project/Repo registry — an ordinary
`SectionRegistry` section, a Sidebar row and `view_stack` page like every
other section. As of 2026-08-19, `project_editor_page.py` is a plain
`QListWidget` of repos (thumbnail icons, grayscale until cloned) plus a
detail panel — see "UI rewrite (2026-08-19)" below — replacing the
`QGraphicsView` node-graph editor (`project_graph_view.py`, removed) that
this section used from 2026-07-15 through then, per the user's own
request to go back to "a dumb list with thumbnails" instead of a pipeline
diagram. Before the 2026-07-20 refactor it was `persistent=True`: never a
sidebar row, docked permanently beside `view_stack` in a `QSplitter`
instead, always visible no matter which ordinary section was currently
showing — folded into the single `view_stack` along with everything else
as part of tightening the app down to one navigation model. Renamed from
`pipeline_architect` on 2026-07-15, when this stopped being a buried
Settings > Developer tab (`ProjectDataEditorPage`, a CRUD tree); briefly a
full-width switchable section the same day, then changed again the same
day to the always-visible docked panel it briefly was.
Three things bundled into one plugin (originally two, before the
2026-07-19 CustomPath addition):

1. **Repo CRUD** — Add/Rename/Delete/Thumbnail Repo, from either the repo
   list's own node context menu or Settings > Project > Project Database's
   "Repositories Database" table (`project_database_page.py`, see the
   "External Plugin Manager merge" section below) — same `MetadataStore`
   calls (`core_api`) the old tree page made, just triggered from
   Settings/list UI instead of tree rows/buttons. There is no Project-level
   CRUD (add/rename/delete/switch project) anywhere in the app — removed
   2026-09-01 along with `project_settings_page.py` (see that bullet
   below), per the user's own call that UkoreHub launches into one project
   per session and switching/managing the Project registry itself was
   never meant to be an in-app feature.
2. **Pipeline connections** — which other repos a given repo has
   connected to, via Repository Setting's "Custom Paths" tab, "Connect
   Input Path" section (moved there 2026-07-19 from a node's right-click
   menu — see `custom_paths_settings_page.py` below). Stored in
   `core/models.py`'s `Repo.plugin_data["project_editor"]` (moved there
   from this plugin's own standalone `PluginConfigStore` file — see the
   `manifest.json` bullet below) — other plugins read it via
   `api.metadata.get_repo_plugin_data(project_id, repo_id, "project_editor")`
   without `core/` needing to know the concept exists.
   As of the 2026-07-15 redesign these are no longer just an editable
   list — they're rendered as directed edges between nodes in the graph,
   which is what actually gives "Pipeline Architect" a visual meaning. As
   of 2026-07-19, each connection points at one specific **CustomPath** a
   repo declares for itself (see below), not the whole repo — a shared
   "...Publish" repo is rarely one undifferentiated destination, so a
   connecting repo needs to say *which* declared location it means. There
   used to be a separate, independently-curated "pipeline outputs"
   concept (a node context menu action "Set as Pipeline Output...")
   alongside this "pipeline inputs" one — **removed 2026-07-19**: every
   connection a repo makes is curated the same single way now, regardless
   of whether the real data flow is "I publish into this" or "I read from
   this" — see `custom_paths_settings_page.py` below and `pipeline_store.py`'s
   `RepoRef` docstring for why. Each connection also carries a `direction`
   (`"input"` or `"output"`, also added 2026-07-19, picked in
   `ConnectInputPathDialog`) — purely cosmetic, it only decides which end
   of the drawn edge the Graph View puts the arrowhead on (into the
   connecting repo for `"input"`, out toward the target repo for
   `"output"`), never the graph's row layout/topology.
3. **CustomPath catalog** — a repo's own list of named locations
   (`{id, label, path}`, `path` relative to that repo's root) other repos'
   pipeline connections pick from — see "Custom Paths" tab
   (`custom_paths_settings_page.py`) below.

## ⚠️ Deliberate architecture tradeoff (unchanged from pipeline_architect)

Creating/renaming/deleting a Project or Repo depends on this plugin loading
successfully — the one place in the app where a plugin load failure has a
real, visible consequence (no way to add/edit/delete repos at all until
it's fixed). See `core/extensibility/loader.py`'s `PluginLoadFailure`
handling for why every other plugin failure is isolated and this one isn't.

`MainWindow._apply_plugin_visibility` never gates this section at all —
there used to be a `manifest.json` `"core": true` flag here, load-bearing
back when this plugin registered a normal switchable section, but it had
already gone fully redundant once the section became `persistent=True`
(now removed, see the top of this file). Removed 2026-08-04 once every
`plugins/core/` plugin (not just this one) became unconditionally visible
for every repo — see `plugins-guide.md`. This plugin's row still shows up,
label-only and unchecked, in the "Core Plugin" list on the "Requirements &
Plugins" tab (`interface/repo_settings/requirements_and_plugins_page.py`),
same as every other `plugins/core/` plugin — nothing plugin-specific
needed here anymore.

## Files

- `manifest.json` — plugin id `project_editor` (renamed from
  `pipeline_architect`; the shared data file at
  `data/plugins/core/project_editor.json` was `git mv`'d in the same
  commit as the folder, so no migration step was needed then). That file
  itself was later superseded by `Repo.plugin_data["project_editor"]`
  (`core/models.py`, `data/projects/<project_id>.json`) — `pipeline_store.py`'s
  `migrate_legacy_data(api)` does a one-time, self-healing cutover of any
  data still in the old blob on `register(api)`.
- `plugin.py` — `register(api)`: constructs `PipelineStore` (passing
  `api.project_plugin_config_store(PLUGIN_ID)` alongside `api.metadata` as
  of 2026-08-19, for the Category catalog — see `pipeline_store.py` below)
  and one `ProjectEditorPage` instance, registers it via
  `api.register_section(...)`
  with `wire=_wire` — `_wire` calls `page.bind_set_active_repo(host.set_active_repo)`
  (so a row selection, or the Clone button, can trigger a real active-repo
  switch without the page holding a `MainWindow` reference) and, added
  2026-09-09 for the Clone button's new behavior (see "Clone / Unclone
  buttons" below),
  `page.bind_navigate_to_submit(lambda: host.navigate_and_focus("repo_git_status", Path()))`
  — `"repo_git_status"` is Submit's `SectionRegistry` key, hardcoded as a
  literal string rather than imported (same convention `submit/plugin.py`
  itself uses for Explorer's `"repo_browser"` key, so this plugin's
  `register(api)` doesn't fail to load if Submit's plugin were ever
  missing/broken). `bind_switch_project`/`bind_open_settings_tab`
  used to be bound here too, for the now-removed "Switch Project..."
  button and "Repository Setting..." row context-menu entry respectively —
  both removed 2026-09-01, see `project_settings_page.py`'s bullet and the
  "Right-click context menu" bullet below.
- `dialogs.py` — `RepoDialog`/`AssignCategoryDialog`/`EditInfoDialog`/
  `ConnectInputPathDialog`/`CustomPathEditDialog` — the latter two moved
  here 2026-09-01 from the now-removed `custom_paths_settings_page.py` (see
  "Settings tabs merged into one" below), now that the module that used to
  justify keeping them apart from this file's own dialogs no longer exists.
  `AssignCategoryDialog` (added 2026-08-19 — a single `QComboBox` of
  "(Uncategorized)" + every existing `Category` + "New Category..."
  (reveals a name field), backing a node's right-click "Assign to
  Category..." action; never talks to `PipelineStore` itself, just hands
  the caller back an existing category id / `None` / a new name to create,
  same as `RepoDialog` handing back plain values for its own caller to act
  on). `RepoDialog` embeds
  `interface/shared/requirements_tree_widget.py`'s `RequirementsTreeWidget`
  (the checkable Program requirements tree, for repo creation) — that
  widget briefly lived in this file (moved in 2026-07-20, moved back out
  2026-08-04 once `interface/repo_settings/requirements_and_plugins_page.py`
  became a second real consumer; see `interface.md`'s `shared/` section).
  Imported as a normal sibling module (`from plugins.core.project_editor.dialogs
  import ...`, the same real-package convention `plugins-guide.md`'s
  "Multi-file plugins" section documents), not a relative import. Used by
  `project_editor_page.py` (`RepoDialog`, repo list's right-click context
  menu Add/Edit Repo, plus `add_repo` — see below). `ProjectDialog`
  (Add New Project.../Rename Project, used by the now-removed
  `project_settings_page.py`) was **removed 2026-09-01** along with that
  file — see that bullet below.
- `project_editor_page.py` — `ProjectEditorPage`: the section's top-level
  widget. As of 2026-08-19 this loads `ProjectEditorTabWindows.ui` at
  runtime via `QUiLoader` (same pattern `custom_paths_settings_page.py`
  uses for `CustomPathWindow.ui`) instead of building a `QGraphicsView`
  node graph in code — see "UI rewrite (2026-08-19)" below for the full
  shape. `current_project_id()`/`add_repo()` remain this page's own single
  source of truth/entry points — `plugin.py` binds these to
  `ProjectDatabasePage`'s `get_current_project_id`/`add_repo` callbacks, so
  a freshly-constructed settings page always reads/acts through to this
  persistent page (matching every `CATEGORY_REPO` tab's own
  self-resolving-active-state convention) rather than holding that state
  itself — clicking Add Repo in Settings takes effect immediately, even
  while that dialog is still open, since it's a plain synchronous call,
  not deferred until the dialog closes (Add Repo's own `RepoDialog` opens
  as a nested modal on top of the already-open Settings dialog, which Qt
  handles fine).
  `set_current_project()` still exists as the one place that actually
  (re)loads a project's repos into the list (also used defensively by
  `set_repo()`, see below), but nothing calls it with a project id other
  than the one fixed at construction anymore. It also defaults the table's
  selection to `local_config_store.active_repo_id` (added 2026-08-19, per
  the user's own request — the table used to open with nothing selected)
  rather than clearing it; `_reload_repo_table()`'s existing per-row
  `repo.id == self._selected_repo_id` check does the actual
  `setCurrentCell()` once that row comes around, same mechanism a
  post-delete/rename reload already relied on to keep whatever was
  selected, selected. There is no in-app way to view a different project
  at all anymore — `bind_switch_project()`/`switch_project()` (which used
  to wrap `UICommandService.switch_project`/`MainWindow._request_switch_project`
  for the now-removed "Switch Project..." button) were removed 2026-09-01
  along with `project_settings_page.py`, see that bullet below; a
  different project means a full relaunch back through `launcher.py`'s
  Project Selector gate. Implements the standard `set_repo()` page
  protocol purely to keep the
  list's bold active-repo row and the detail panel in sync when the active
  repo changes elsewhere — this page only *reacts* to active-repo changes
  except when the user selects an already-cloned row (see "Selecting a
  row" below).
- `project_settings_page.py` — **removed 2026-09-01**, per the user's own
  call. Used to hold `ProjectSettingsPage`, a `CATEGORY_PROJECT` Settings
  tab ("Project", added 2026-08-03) with Rename Project/Delete Project/Add
  Repo/"New Project..."/"Switch Project..." buttons. None of those
  survived: Add Repo was already duplicated by Project Database's own
  "Repositories Database" table (`project_database_page.py`, see the
  "External Plugin Manager merge" section below); Rename/Delete/New/Switch
  Project were cut outright rather than moved anywhere, on the reasoning
  that managing/switching the Project registry itself was never meant to
  be an in-app feature — UkoreHub launches into one project per session
  via `launcher.py`'s mandatory Project Selector gate and stays there for
  the whole run, full stop. `dialogs.py`'s `ProjectDialog` (this page's
  only consumer) was removed in the same change — see that bullet above.
- `project_graph_view.py` — **removed 2026-08-19**, see "UI rewrite
  (2026-08-19)" below. Used to hold `ProjectGraphView` (`QGraphicsView`),
  `RepoNodeItem`, `PipelineEdgeItem`, and `CategoryBoxItem` — the node
  graph this plugin used from 2026-07-15 through then.
- `repo_status_scan_worker.py` — `RepoStatusScanWorker` (`QThread`): the
  table's Status column background check — see the "Status column" bullet
  below. Continues past a single repo's failure, since one repo's git
  status has no bearing on any other row. A deliberate local duplicate of
  `plugins/core/submit/git_stream_worker.py`'s
  QThread-wraps-a-callable/`finished_ok`/`failed` shape rather than an
  import of it — this plugin doesn't reach into a sibling plugin's source
  (see "Working here" at the bottom of this file).
  `required_repo_clone_worker.py` (`RequiredRepoCloneWorker`) used to live
  here too, backing the Clone button's own blocking `QProgressDialog`
  clone — **removed 2026-09-09** per the user's own request, since it
  duplicated Submit's already-existing first-clone handling (see "Clone /
  Unclone buttons" below) with a second, redundant loading dialog.
- `sync_engine.py`, `sync_worker.py`, `sync_status_store.py`,
  `last_check_store.py`, `external_plugin_updater_page.py`,
  `ExternalPluginUpdaterWindow.ui` — moved here from the former
  `plugins/core/ExternalPluginManager/` plugin (merged in 2026-09-01, that
  plugin's folder deleted) — see "External Plugin Manager fully merged in"
  below for what each does.

## External Plugin Manager merge (2026-09): Project Database + Repository Settings

**Superseded 2026-09-01 — see "Settings tabs merged into one" below.** The
two Settings tabs this section describes (`ProjectDatabasePage`,
`RepoSettingsPage`) no longer exist as separate tabs/files; their logic now
lives inside `project_editor_settings_page.py`'s single merged
`ProjectEditorSettingsPage`, under its "Repo Database" / "Program and
External Plugin Database" / "Repo Enable Plugins and Programs" sub-tabs.
This section is kept for the per-widget/per-field history (still accurate
— only the file/class/tab-registration layer changed, not the widgets or
their logic), but any `project_database_page.py`/`repo_settings_page.py`/
`ProjectDatabaseWindow.ui`/`RepoSettingsWindow.ui` file reference below is
stale.

Two more CATEGORY_PROJECT Settings tabs, added when
`plugins/core/ExternalPluginManager/`'s catalog-CRUD tab and the old
builtin "Program Database"/"Requirements & Plugins" tabs were consolidated
here, per the user's own request:

- `project_database_page.py` — `ProjectDatabasePage`: Settings > Project >
  "Project Database" (key `project_editor_project_database`, order 20),
  UI authored in Qt Designer (`ProjectDatabaseWindow.ui`, same `QUiLoader`
  pattern this plugin already uses elsewhere). Three `QGroupBox`es side by
  side, each its own CRUD table:
  - **Program Database** (`tableWidget_project_program_database`) — moved
    from the old builtin `interface/settings/program_database_page.py`
    tab (removed). Same `MetadataStore.list_programs`/`add_program`/
    `edit_program`/`delete_program` calls, `interface/settings/program_dialog.py`'s
    `ProgramDialog` for Add/Edit (re-exported through `interface_api`/
    `plugin_api` specifically for this — see `developer/app/docs/interface-api.md`).
  - **External Plugins Database** (`tableWidget_external_plugin_database`)
    — originally moved from `plugins/core/ExternalPluginManager/`'s old
    "External Plugin Manager" tab (`external_plugins_page.py`, removed) as
    this section's own catalog-CRUD-only piece of that first merge pass;
    that whole plugin was folded into this one outright on 2026-09-01 (see
    "External Plugin Manager fully merged in" below), so there's no sibling
    plugin left at all now. Add/Edit/Remove a catalog entry's name/git_url/
    folder_name (the table itself only shows Name/Requires — Git URL and
    Folder Name columns were cut 2026-09-01, per the user's own request;
    the Edit dialog still edits both fields, just not shown as their own
    table columns). Cloning/pull/status is this same plugin's
    `_SyncController`/`ExternalPluginUpdaterPage` job now (Settings >
    Account > Plugins). Reads/writes
    `Project.plugin_data["external_plugins"]["catalog"]` via this file's
    own `external_plugin_catalog.py` (`ExternalPluginCatalog`/`CatalogEntry`
    — the one canonical definition now, not a duplicate of anything) and
    `external_plugin_dialog.py` (`ExternalPluginCatalogEntryDialog`).
    `plugin.py`'s `register(api)` builds one
    `ExternalPluginCatalog(api.project_plugin_config_store("external_plugins"))`
    instance and passes it to every consumer (this tab, the sync engine,
    the Updater page) — `"external_plugins"` is kept as the storage
    `plugin_id` unchanged from the original ExternalPluginManager plugin,
    for on-disk data compatibility (see "External Plugin Manager fully
    merged in" below).
  - **Repositories Database** (`tableWidget_project_repositories_database`)
    — new. Add/Edit(rename)/Remove(delete) a repo; the table itself only
    shows a Name column (Git URL was cut 2026-09-01, per the user's own
    request — still editable via the Edit dialog, just not its own table
    column). Delegates every mutation to
    `ProjectEditorPage.add_repo`/`rename_repo`/`delete_repo`
    (the latter two thin public wrappers added around the existing
    `_rename_repo`/`_delete_repo` the table's own right-click menu already
    used — see `project_editor_page.py` above) so the persistent
    `ProjectEditorPage` table stays the single source of truth and
    refreshes itself the same way regardless of which entry point was
    used.
- `repo_settings_page.py` — `RepoSettingsPage`: Settings > Project >
  "Repository Settings" (key `project_editor_repo_settings`, order 21), UI
  authored in Qt Designer (`RepoSettingsWindow.ui`). Replaces the old
  builtin CATEGORY_REPO "Requirements & Plugins" tab
  (`interface/repo_settings/requirements_and_plugins_page.py`'s
  `RequirementsAndPluginsPage`, removed) — that tab always edited whichever
  repo was currently *active*; this one lets an admin edit **any** repo in
  the project without switching the active repo first, per the user's own
  request when merging External Plugin Manager in. Three `QGroupBox`es:
  - **Repositories** (`tableWidget_repositories`) — every repo in the
    active project, single-selection, name only. Purely a picker —
    selecting a row swaps which repo's requirements the other two
    groupboxes show/edit; it never clones, activates, or changes anything
    on its own. Defaults to whichever repo is currently active
    (`local_config_store.active_repo_id`) on first load, same convention
    `project_editor_page.py`'s own table already uses.
  - **Enable Programs** (`groupBox`/`tableWidget_project_enable_program`)
    — the `.ui`'s placeholder table is swapped out on every selection
    change for a real `RequirementsTreeWidget` instance (same pattern
    `RequirementsAndPluginsPage` used for its own placeholder
    `QTreeWidget`), editing the *selected* repo's
    `required_program_ids`/`program_version_pins`.
  - **Enable Plugins** (`groupBox_4`/`tableWidget_external_enable_plugins`,
    four columns: checkbox, plugin name, requires, info) — ported
    near-verbatim from `RequirementsAndPluginsPage` (clone-on-check for a
    not-yet-cloned catalog entry, cross-plugin `PluginManifest.requires`
    enforcement, the `Error`/`Not Clone`/etc. Info-column text), scoped to
    the *selected* repo instead of the active one. Reads the same
    `Project.plugin_data["external_plugins"]["catalog"]` raw dicts via
    `store.get_project_plugin_data` the old page did — no
    `ExternalPluginCatalog` dependency needed here, only CRUD (the
    Project Database tab, above) needs that class.

Both new tabs (now sub-tabs, see below) are `CATEGORY_PROJECT`, not
`CATEGORY_REPO` — deliberate, since neither is scoped to "the currently
active repo" anymore (Project Database is project-wide catalogs;
Repository Settings has its own independent repo picker). The former
`custom_paths_settings_page.py`'s "Custom Paths" tab joined them as a
third `CATEGORY_PROJECT` entry on 2026-09-01 (see its own bullet below) —
that move was purely cosmetic (which Settings header it renders under),
not a scope change: unlike the other two, it's still scoped to "the
currently active repo" internally, same self-resolving-active-repo
`refresh()` as before. `interface/settings/settings_view.py`'s
`_REPOSITORY_KEYS` (the "Repository" Settings group) no longer includes a
Requirements & Plugins entry as a result — see that file's own comment.

## External Plugin Manager fully merged in (2026-09-01)

`plugins/core/ExternalPluginManager/` — everything that plugin still had
left after the CRUD-only first pass above — was merged into this plugin
outright and the folder deleted, per the user's own request ("จัดการเลย
ผมต้องการย้ายเข้าไปใน Project Editor"). Six files moved here unchanged
except for import paths (`plugins.core.ExternalPluginManager.X` →
`plugins.core.project_editor.X`): `sync_engine.py`, `sync_worker.py`,
`sync_status_store.py`, `last_check_store.py`,
`external_plugin_updater_page.py`, `ExternalPluginUpdaterWindow.ui`. The
duplicate `catalog_store.py`/`CatalogEntry`/`ExternalPluginCatalog` that
plugin used to carry was dropped — this plugin's own
`external_plugin_catalog.py` (already the CRUD side's definition, see
above) became the one canonical version, gaining the `update_plugin_id()`
method the sync engine needs (previously only on the other copy). Every
consumer — CRUD (Project Database tab), the sync engine, the Updater
page — now shares the exact same `ExternalPluginCatalog` instance, built
once in `plugin.py`'s `register()`, instead of three separate wrapper
objects reading the same underlying store.

**Storage compatibility, unchanged:** the merged code keeps
`"external_plugins"` as the `plugin_id` string for both
`api.project_plugin_config_store()` (the catalog itself,
`Project.plugin_data["external_plugins"]["catalog"]`) and
`api.plugin_config_store(..., shared=False)` (the per-machine
`sync_status`/`last_check_result` keys) — deliberately **not** renamed to
`"project_editor"`, which would have orphaned every existing project's
catalog and every machine's cached sync/check results. `manifest.json`'s
own plugin `id` (`"external_plugins"`, distinct from the storage key
despite sharing the string) is gone along with the rest of that plugin's
`manifest.json` — nothing else in the app declared it as a `requires`
target, so no dependency-graph fallout.

**Auto-sync moved to Portal (2026-09-30):** `_SyncController`,
`sync_worker.py`, and the "Force update and restart UkoreHub" popup are
**gone** — per the user's own request, since restarting right after launch
made no sense. `portal/plugin_update.py` now runs after sign-in, right
before Portal spawns `app/launcher.py`: fetch + `merge --ff-only` for
every clone under `cache/plugins/` (never resets — a clone with local
commits/edits just fails the fast-forward, is logged, and is left as-is),
plus clone-if-missing for catalog entries required by the active
project's locally-cloned repos (and the active repo), read from
`data/projects/<id>.json` — which Portal itself has just pulled from R2
(`portal/cloud_sync.py`), for the project just picked in Portal's own
project combobox (`portal/main.py`'s `_on_cloud_synced`). What's left here:
`_backfill_catalog_plugin_ids` on `on_app_start` (Portal needs
`CatalogEntry.plugin_id` set to map required ids to entries),
`sync_engine.py` trimmed to the status constants the Updater page still
reads, and the manual Settings > Account > Plugins tab, unchanged. The
paragraph below is history.

**What moved into `plugin.py`:** `_SyncController` (byte-for-byte the same
class, just built with an injected `catalog` param now instead of
constructing its own) is built once in `register()` and subscribed to
`api.on_app_start`/`api.on_repo_changed` — the same lifecycle wiring
ExternalPluginManager used, now living here instead. It owns the
auto-sync engine (clone-if-missing / check-if-behind every External
Plugins catalog entry the active repo's `Repo.required_plugin_ids`
resolves to, via `sync_worker.ExternalPluginSyncWorker`, a real `QThread`
so it never blocks app start or a repo switch) and the "Force update and
restart UkoreHub" / "Ignore" popup for anything found behind (never
auto-pulls — `discover_plugins()`/`apply_plugins()` are one-shot at
startup, so a silent pull wouldn't take effect until a restart anyway).
The `"Plugins"` Settings tab (`external_plugins_updater`,
`CATEGORY_GENERAL`, order 10, Settings > **Account** — not Project, since
it's day-to-day operational status, not registry admin) renders
`ExternalPluginUpdaterPage`: a 4-column table (Name/Status/Detail/Last
Checked) with **Check for Status** (parallel per-row `QThreadPool` fetch,
`_MAX_PARALLEL_CHECKS = 8` — every entry lives in its own
`cache/plugins/<folder>` clone, so no two tasks ever race the same
folder), **Update All** (sequential, force-updates every entry, one
confirm prompt — destructive, so correctness beats speed here), and a
per-row right-click menu (**Clone** / **Unclone** / **Open Directory** /
**Bulk Push**, each enabled/disabled per that row's live git state). The
logger name `logging.getLogger("ExternalPluginManager")` (`plugin.py`,
also `launcher.py`'s own repo-plugin load/register-result logger) was
**kept unchanged** rather than renamed to match this folder — DebugConsole
log continuity for anyone already filtering on that source name mattered
more than the name matching where the code now lives.

**Status buckets** (`external_plugin_updater_page.py`) are exactly 5:
`Error`, `Not Clone`, `Modified`, `Update Needed`, `Up to date` — anything
more specific (ahead/behind counts, conflict instructions, broken-git
instructions) goes in the **Detail** column instead of being its own
bucket. `_local_status` (fast, local-only, every `refresh_list()`) checks
live git state first (`is_cloned` → `is_repo_root` → `has_unresolved_merge`
→ working-tree dirty) and only falls back to `sync_status_store`'s
persisted result *within the branch it applies to* — a stale persisted
error can never override real, current, local git state.
`sync_status_store.py`'s `sync_status` key (auto-sync's own
conflict/error/broken-git memory) and `last_check_store.py`'s separate
`last_check_result` key (the last manual Check for Status result) are
deliberately two different top-level JSON keys in the same per-machine
`plugin_local_config/external_plugins.json` file, specifically so the
auto-sync engine's own set/clear-on-success calls can never wipe out a
manual check's cached result.

**Why `is_repo_root`, not just `is_cloned`:** `GitService.is_cloned()`
only checks that a `.git` entry exists — true even for an empty/corrupt
`.git` left by an interrupted clone, in which case git's own
repo-discovery silently walks up to whatever real repository is further
up the tree (in this app's case, UkoreHub's own repo root) instead of
failing. Update All/Check for Status/Bulk Push all gate on
`GitService.is_repo_root()` instead, which actually confirms `git
rev-parse --show-toplevel` resolves back to the folder itself — see the
`ukorehub-core` skill; a broken `cache/plugins/AdvancedSkeleton/.git` once
almost caused Bulk Push to commit and push UkoreHub's own uncommitted
local changes into `AdvancedSkeleton`'s remote.

**Why "Check for Status" alone uses a `QThreadPool`, everything else stays
synchronous:** opening the tab is a fast local-only pass (no network).
Clone/Unclone/Open Directory/Bulk Push and Update All still call git over
the network but run synchronously on the UI thread (`WaitCursor`) — each
is one deliberate click, not worth threading on its own. Check for Status
is the one action that routinely touches *every* row in a single click, so
it's the one place a large catalog's worth of sequential round-trips would
actually be felt; Update All stays sequential anyway since force-updating
is destructive and correctness matters more than speed there. The
auto-sync engine is a different situation again — it fires unattended on
every app start/repo switch and may need to touch several plugins
sequentially without blocking startup, so it uses a real `QThread`
(`sync_worker.py`) rather than either of the page's own patterns.

**Per-project catalog history:** before 2026-08-11 (well before this
merge) the catalog was one studio-wide file
(`data/plugins/core/external_plugins.json`, `shared=True`), later moved
into each `Project.plugin_data["external_plugins"]["catalog"]` instead —
see `external_plugin_catalog.py`'s own docstring and this file's git
history if the full story is ever needed; that old shared file is left on
disk, unread by anything.

## UI rewrite (2026-08-19): list + detail panel, replacing the node graph

`project_editor_page.py` loads `ProjectEditorTabWindows.ui` (Qt Designer,
same `QUiLoader` pattern `custom_paths_settings_page.py` uses for
`CustomPathWindow.ui`) instead of building a `QGraphicsView` scene in code
— per the user's own request to go back to "a dumb list with thumbnails"
instead of a pipeline diagram. `groupBox_repositories_requirements` in the
`.ui` shipped with no child widget; a `QListWidget`
(`listWidget_repositories_requirements`, matching the sibling
`listWidget_software_requirements` groupbox's own layout shape) was added
to it directly in the `.ui` XML rather than built in Python, so Designer
still round-trips the whole layout. The user then hand-edited the `.ui` a
second time the same day (still 2026-08-19) — swapping the repo
`QListWidget` for a `QTableWidget`, dropping the Assign Categories button,
and adding an Info groupbox — see "Second pass" below for that revision.

- **`tableWidget_Repo`** (`QTableWidget`, 5 columns —
  `_COL_NAME`/`_COL_CLONED`/`_COL_EDITED`/`_COL_CONNECTION`/`_COL_ACCESS`,
  `SelectRows`/`SingleSelection`/`NoEditTriggers`) — one row per repo in
  the loaded project (`project.repos`' own order — no category grouping;
  see "Second pass" for why Category assignment is gone). The active
  repo's Name cell renders bold — the only "active" affordance left
  besides the Connection column; there's no more HUD overlay (see "What
  was dropped" below). Each row's repo id rides on the Name cell's
  `Qt.UserRole` data now (`_on_repo_selection_changed`,
  `_on_repo_context_menu` both read it from `_COL_NAME`).
  A dedicated Thumbnail column (with a large `160x90` icon, a matching
  fixed row height, and a `_FixedIconDelegate` class so the small
  Status/Connection standard-icon pixmaps wouldn't get upscaled to fill
  that same big box) briefly existed but was **removed same-day
  (2026-08-19)** — the user reported the Status/Connection icons weren't
  showing at all even after widening those columns, and asked to drop the
  Thumbnail column and put sizing back to normal to see if that alone
  fixed it. With no oversized column forcing a table-wide `iconSize()`,
  the `_FixedIconDelegate` workaround (and its Status/Connection
  `QHeaderView.Fixed`-plus-explicit-width follow-up, tried first and
  reported still not working) is gone too — `repo_table.setIconSize(_STATUS_ICON_SIZE)`
  (`QSize(18, 18)`) plus plain `QTableWidgetItem.setIcon()` and
  `QHeaderView.ResizeToContents` on both columns is the whole story now,
  same as any other icon column in this codebase. The repo's own
  thumbnail image (`MetadataStore.resolve_thumbnail_path(repo)`,
  grayscale via `_grayscale` while not cloned) still exists — it just
  renders in the detail panel's `label_images` and the
  `listWidget_repositories_requirements` icons (`_repo_icon`, sized via
  `_REPO_ICON_SIZE`, renamed from `_REPO_TABLE_ICON_SIZE` since it's no
  longer table-specific) rather than as a table column.
- **Cloned/Edited/Access columns — icon-or-blank, 2026-09-12 redesign**:
  these three (plus Connection, unchanged below) all follow one convention
  now, per the user's own request — a blank cell is always the
  default/unremarkable case, and a single custom PNG (`icons/cloned.png`/
  `icons/edited.png`/`icons/locked.png`, this plugin's own
  `icons/` folder, loaded once per `ProjectEditorPage` instance as
  `self._cloned_icon`/`self._edited_icon`/`self._locked_icon` in
  `__init__` — needs a live `QApplication` to construct a `QPixmap` from,
  so these can't be module-level constants) is the one state worth calling
  out. This replaces an earlier design (still visible in git history) that
  used `QStyle` standard icons for a multi-state "Status" column
  (not-cloned/syncing/modified/up-to-date/check-failed) plus a similar
  multi-state Access column — both collapsed into simpler binary columns
  here.
  - **Cloned column** (`_COL_CLONED`, `_set_cloned_cell`) — `cloned.png` if
    `GitService.is_cloned` (same synchronous check the detail panel's
    thumbnail grayscale already uses), blank otherwise. No background scan
    needed, known immediately in `_reload_repo_table`.
  - **Edited column** (`_COL_EDITED`, `_set_edited_cell`) — `edited.png`
    only if the repo has uncommitted working-tree changes, blank for
    everything else (clean, not yet cloned, still checking, or the check
    itself failed — `_on_status_failed` deliberately treats a failed check
    the same as "no evidence of a change" rather than guessing). Still
    background-checked by `RepoStatusScanWorker`
    (`repo_status_scan_worker.py` — a local duplicate of
    `submit/git_stream_worker.py`'s shape, same boundary rule
    `required_repo_clone_worker.py` already follows) running
    `GitService.get_status` per **cloned** repo only (this column is the
    one of the three that still needs a local clone to check at all) —
    `_status_scan_token`/`_status_workers` unchanged from before, still
    guard against a superseded scan and keep a running `QThread` alive
    until it finishes.
  - **Access column** (`_COL_ACCESS`, `_set_access_cell`) — added after an
    artist's push kept hitting GitHub's `Permission to <owner>/<repo>.git
    denied to <user>` (a 403) with no earlier signal anywhere in the app
    that the signed-in account wasn't a collaborator with write access.
    `locked.png` only when push access is *confirmed* denied; blank for
    both "has push access" and "couldn't be checked" (a non-github.com
    remote, no signed-in token, or a network/API error,
    `_on_access_unknown`) — deliberately the same blank as "has access" so
    "can't check" is never mistaken for "confirmed no access". Background-
    checked by `RepoAccessScanWorker` (`repo_access_scan_worker.py`, a
    local duplicate of `RepoStatusScanWorker`'s QThread-wraps-a-callable
    shape) via `core_api`/`plugin_api`'s `get_repo_permissions(owner,
    repo, token)` (`core/vcs/repo_access.py` — same `GET
    /repos/{owner}/{repo}` endpoint `check_repo_access` already hits, just
    reading the response body's own `permissions` object instead of
    discarding it). Unlike the Edited column's scan, this one runs for
    **every** repo in the table regardless of clone state
    (`_reload_repo_table` builds `access_targets` from `repo.git_url`
    unconditionally) — it's a pure GitHub API call, no local clone needed
    to ask "could I push here." `_access_scan_token` (bumped alongside
    `_status_scan_token` on every `_reload_repo_table()`) drops a result
    from a superseded scan the same way the Edited column's own token
    does. Public/private repo visibility is irrelevant here — a public
    repo is freely clone/pull-able by anyone, but push still always
    requires being a collaborator with write access, which is exactly what
    this column checks and none of the others could surface.
- **Connection column** (`_refresh_connection_column`) — only lights up
  for a row the currently **active** repo (not the *selected* row) has a
  Custom Paths connection to: reads `PipelineStore.get_inputs(project_id,
  active_repo_id)` and, for each `RepoRef` whose target is a row in this
  table, sets `QStyle.SP_MediaSkipBackward` for an `"input"` connection or
  `SP_MediaSkipForward` for `"output"` — a quick-glance replacement for
  the old graph's directed edges, per the user's own request. Recomputed
  on every `_reload_repo_table()` and, cheaply (no table rebuild), on
  every pure active-repo switch via `set_repo()`. Still uses `QStyle`
  standard icons, not a custom PNG — untouched by the 2026-09-12 redesign
  above since it's a two-way "input vs. output", not an icon-or-blank
  column.
- **Selecting a row** (`_on_repo_selection_changed`, via `currentRow()`)
  only refreshes the detail panel — it deliberately never clones anything
  and never changes the active repo unless the selected repo is *already*
  cloned (in which case it calls the bound `set_active_repo` callback,
  deferred one event-loop tick via `QTimer.singleShot(0, ...)` since that
  call can round-trip back into this page's own `set_repo()`, updating
  this very table while the `itemSelectionChanged` signal that triggered
  it is still on the call stack). Cloning is only ever triggered by the
  **Clone** button, never by selection — the one deliberate behavior
  change from the old graph's single-click-clones-and-switches flow, per
  the user's own request that selecting a repo shouldn't clone it or
  switch to it "until we've already cloned that repo".
- **Detail panel** (right side of the `.ui`, `_refresh_detail_panel`):
  `label_images` shows the selected repo's thumbnail scaled to
  `_PREVIEW_MAX_SIZE`, grayscale under the same not-cloned rule
  (`_grayscale`/`_is_repo_cloned`) as everywhere else. `listWidget_software_requirements`
  stays icon-only (`QListWidgetItem(icon, "")`, `IconMode`/`Static`/no
  selection, program name only in the tooltip) per
  `repo.required_program_ids`, resolved via
  `MetadataStore.get_program`/`resolve_program_icon_path` — the user's own
  "just the program icon" request.
  There used to also be a `listWidget_repositories_requirements`
  (`ListMode`, `PipelineStore.get_required_repos` — the selected repo's own
  direct pipeline-input dependencies, reusing a `_repo_icon` helper) right
  below it — **removed same-day (2026-08-19)**, per the user's own call
  that it was redundant with the table's own Connection column (a
  quick-glance icon is enough, no need for a second, duplicate list of the
  same dependency info). The `.ui` groupbox/list widget was cut first (by
  hand); this plugin's Python code was cleaned up to match —
  `repositories_requirements_list`, `_reload_repositories_requirements()`,
  and the now-unused `_repo_icon()`/`_REPO_ICON_SIZE` helper are all gone.
  `PipelineStore.get_required_repos` itself is untouched (same
  "leave the data-layer method in place, just cut the caller" precedent as
  the Category catalog below).
- **Info panel** (`groupBox_2`/`textBrowser_info`/`pushButton_edit_info`,
  added in the "Second pass") — a free-form per-repo note,
  `PipelineStore.get_repo_info`/`set_repo_info`, stored on
  `Repo.plugin_data["project_editor"]["info"]` (plain string, empty if
  never set) — same field this plugin already uses for
  `pipeline_inputs`/`custom_paths`/`category_id`, so it rides along on
  that project's own already-cloud-synced blob (`data/projects/<id>.json`)
  with zero extra sync plumbing, satisfying the user's "sync to the cloud"
  ask for free. `textBrowser_info` is read-only display
  (`_refresh_detail_panel`'s `setPlainText`); `pushButton_edit_info` opens
  `dialogs.py`'s `EditInfoDialog` (a single big `QPlainTextEdit` +
  OK/Cancel, same "hand the caller back a plain value" convention every
  other dialog in that file follows) pre-filled with the current text,
  saving through `PipelineStore.set_repo_info` on accept.
- **Set Thumbnail button** (`pushButton_set_thubmnail` — a typo in the
  `.ui`'s own object name, "thubmnail", matched verbatim in
  `findChild(QPushButton, "pushButton_set_thubmnail")` since renaming it
  in Python wouldn't reach the real widget; the *display* text still reads
  "Set Thumbnail"; fix the object name in Designer first if this ever gets
  cleaned up, then update the `findChild` call in the same change) — added
  next to Edit Info, a follow-up ask on top of the "Second pass" below.
  `_on_set_thumbnail_clicked` just delegates to the same
  `_change_repo_thumbnail(project_id, repo_id)` the right-click context
  menu's "Change Thumbnail..." already calls — a second, easier-to-find
  entry point for the same action, not a new implementation.
- **Open Local Directory button** (`pushButton_open_local_directory`,
  added 2026-09-01, next to Set Thumbnail/Edit Info) — opens the
  *selected* repo's local clone folder in the OS file explorer via
  `plugin_api.open_in_file_explorer` (`core/os_utils.py`'s
  `open_in_file_explorer`, already used the same way by
  `ExternalPluginManager`'s own "Open Directory" — see that plugin's doc).
  Disabled unless a cloned repo is selected (`_update_detail_controls`).
  Added alongside removing the builtin "Local Repository" Settings tab —
  covers the "where does this actually live on disk" half of what that tab
  was for; Unclone below already covered the other half.
- **Clone / Unclone buttons** — act on whichever repo is currently
  *selected* in the table (`_selected_repo_id`, independent of the active
  repo). Clone (disabled once already cloned) confirms, then **doesn't
  clone anything itself** (`_on_clone_clicked` — the old blocking
  `QProgressDialog`/`RequiredRepoCloneWorker` path, itself a descendant of
  `ProjectGraphView._clone_required_repos`'s cascading-clone dialog, was
  **removed 2026-09-09** per the user's own request): it switches the
  active repo to the selected one and jumps straight to the Submit tab
  (`UICommandService.navigate_and_focus("repo_git_status", ...)`, bound via
  `plugin.py`'s new `bind_navigate_to_submit` — the `path` argument is an
  unused placeholder, since Submit's page doesn't implement
  `PathFocusablePage`), whose own "Sync New Commit"
  (`submit/repo_git_status_page.py`'s `start_sync`) already clones a
  not-yet-cloned repo before syncing, with its own progress/log feedback —
  no second, redundant loading dialog needed here. Both callback
  invocations are deferred one event-loop tick
  (`QTimer.singleShot(0, ...)`), same reasoning as the row-selection
  handler below: `set_active_repo` can round-trip back into this page's
  own `set_repo()`. Unclone (disabled while not cloned) confirms, then
  `shutil.rmtree`s `workspace_root / repo.local_path` and calls
  `MetadataStore.mark_status(project_id, repo_id, "not_cloned")` — the
  same operation the builtin "Local Repository" Settings tab's "Remove
  Local Repositories" button used to perform (that tab was removed
  2026-09-01 as redundant with this button — see
  `project_settings_page.py`'s bullet above), just reachable per-repo from
  this table instead of only for the currently-active repo.
- **Right-click context menu** on a table row — "Rename Repo...", "Change
  Thumbnail...", "Delete Repo" (no "Assign to Category..." entry anymore,
  see "Second pass" below). There used to also be a "Repository
  Setting..." entry, opening the unified Settings dialog via
  `bind_open_settings_tab`/`UICommandService.open_settings_tab` on the
  builtin "Local Repository" tab for whichever repo was currently *active*
  — removed 2026-09-01 along with that tab, since it had nothing left to
  jump to (see `project_settings_page.py`'s bullet above).

**What was dropped, not just moved:** the bottom-right HUD overlay
(project name, active repo, `Repo.last_synced`, Input/Output Custom Path
lines) has no replacement in the new `.ui` — it wasn't part of what the
user asked to keep. Pipeline connections are still fully visible via
`custom_paths_settings_page.py`'s "Connect Input Path" section (unchanged),
the table's own Connection column, and `listWidget_repositories_requirements`
above; `Repo.last_synced` has no UI surface in this plugin at all anymore
(`Repo.status` does, sort of — the table's Status column is a *live*
git-status check now, not a read of the stored field, which the HUD used
to show verbatim). The pipeline-dependency auto-clone cascade (cloning a
repo's required repos automatically when switching to it) is also gone —
see the `required_repo_clone_worker.py` bullet above for why.

## Second pass (still 2026-08-19): table, Info panel, no more Categories

Same day as the list rewrite above, the user hand-edited
`ProjectEditorTabWindows.ui` again and asked for three more changes,
folded into the same files rather than kept as a separate revision:

1. **`listWidget_Repo` → `tableWidget_Repo`** — a `QTableWidget` with the
   Status/Connection columns described above, "using the same logic as
   the Submit tab's icon" for Status. Documented inline in the bullets
   above rather than as a separate section, since the table *is* now the
   plugin's repo list, not an alternate view of it.
2. **Assign Categories cut entirely** — `pushButton_5` and its Assign
   Categories handler are gone from both the `.ui` and
   `project_editor_page.py` (no button, no context-menu entry), per the
   user's own "I don't think it's necessary, just cut it" call.
   `PipelineStore.get_repo_category_id`/`set_repo_category_id`/
   `get_categories`/`add_category`/`set_categories` and `dialogs.py`'s
   `AssignCategoryDialog` are all still present but **currently
   unreachable from any UI** — left in place rather than deleted since a
   real repo may already have a `category_id` saved from the brief window
   this was live, and deleting the data-layer methods would be a bigger
   call than "cut the button" asked for. Worth a real cleanup pass later
   if the feature stays unwanted.
3. **Info panel added** — `textBrowser_info`/`pushButton_edit_info`,
   documented in the "Info panel" bullet above.
- `repo_settings_panel.py` (**removed** as part of the 2026-07-20 refactor
  — `RepoSettingsPanel`/`RepoSettingsDialog` used to render every
  `CATEGORY_REPO` `SettingsTabSpec` in its own popup, opened via a node's
  right-click "Repository Setting...", so these tabs weren't editable from
  both there and the app-level Setting dialog at once. Those tabs render
  inside `interface/settings/settings_view.py`'s single Plugins group
  instead now — see `interface.md`'s `settings/` "Rendering history"
  note. `project_editor_page.py`'s own `_open_repo_settings()` (formerly
  `ProjectGraphView.open_repo_settings()`, before the 2026-08-19 UI
  rewrite) used to open that same dialog on the builtin "Local Repository"
  tab via `UICommandService.open_settings_tab` — removed 2026-09-01 along
  with that tab, see the "Right-click context menu" bullet above).
- `pipeline_store.py` — `PipelineStore`/`RepoRef`/`CustomPath`. Lives in each
  repo's own `Repo.plugin_data["project_editor"]` (`core/models.py`,
  `data/projects/<project_id>.json` — moved off the old standalone
  `data/plugins/core/project_editor.json` blob; `migrate_legacy_data(api)`
  in this same file does the one-time cutover). Per-repo shape:
  ```json
  {
    "pipeline_inputs": [{"project_id": "...", "repo_id": "...", "custom_path_id": "...", "direction": "input"}],
    "custom_paths": [{"id": "...", "label": "Character", "path": "Character"}],
    "category_id": "..."
  }
  ```
  `category_id` (added 2026-08-19) is this repo's own `Category`
  assignment, set via the list's "Assign Categories" button/context-menu
  action (`project_editor_page.py`'s `_on_assign_category_clicked`) —
  `null`/missing just means unassigned; nothing currently groups or
  reorders the list by it (see "UI rewrite (2026-08-19)" above — this used
  to drive `ProjectGraphView`'s node-grid layout before the graph was
  removed the same day). The `Category` catalog itself (`{id, name}`) is
  **not** per-repo — it's scoped to the whole active Project instead,
  stored at `Project.plugin_data["project_editor"]["categories"]` via
  `api.project_plugin_config_store(PLUGIN_ID)` (`PipelineStore.__init__`'s
  `project_config_store` param, `get_categories`/`add_category`/
  `set_categories`), riding on
  that project's own already-cloud-synced blob rather than a separate file
  — same mechanism `ExternalPluginManager` already uses for its own
  project-scoped catalog, see `plugins-guide.md`. `Category.id` is a
  stable `uuid4` (not derived from `name`) so renaming one doesn't
  invalidate every repo's own `category_id` pointing at it.
  There used to also be a `"pipeline_outputs"` key here (a separate,
  independently-curated list, written by a now-removed "Set as Pipeline
  Output..." context-menu action) — **removed 2026-07-19**; every
  connection a repo makes is a `"pipeline_inputs"` entry now (see the
  "Pipeline connections" bullet at the top of this file for why).
  `RepoRef.custom_path_id` is looked up against the **target** repo's own
  `custom_paths` entry (`PipelineStore.get_custom_path(target_project_id,
  target_repo_id, custom_path_id)`) — it's meaningless without also
  knowing which repo it belongs to, since ids are only unique within one
  repo's own list, not globally. `custom_path_id=None` is only possible on
  data saved before this field existed; every ref created through
  `CustomPathsSettingsPage`'s "Connect Input Path" section now requires
  picking one. `CustomPath.id` is a stable `uuid4` (not derived from
  `label`) so renaming one doesn't invalidate every `RepoRef` already
  pointing at it. `RepoRef.direction` (added 2026-07-19) defaults to
  `"input"` for any ref saved before the field existed — see `RepoRef`'s
  own docstring (the arrowhead direction it drove is moot now that the
  graph that drew arrows is gone, but the field and its default still
  round-trip on old data unchanged). `get_custom_paths`/`get_custom_path`
  swallow `NotFoundError` for a target repo that no longer exists
  (2026-09-14 fix) — deleting a repo doesn't clean up other repos'
  `pipeline_inputs` refs pointing at it (`project_editor_page.py`'s
  `_delete_repo` has no such cleanup step), and
  `project_editor_settings_page.py`'s `_rebuild_connected_table` resolves
  every stale ref's custom path on every Settings-dialog open — before this
  fix, one dangling ref to a deleted repo crashed the whole Setting dialog
  (`NotFoundError` propagating out of `MetadataStore.get_repo`) instead of
  rendering the `"(deleted custom path)"` row it already had a fallback
  string for.
  `get_required_repos(project_id, repo_id)` resolves a repo's own direct
  `pipeline_inputs` refs into the actual target `Repo` objects (deduped,
  direct-only — no recursion into each target's own inputs), used by
  `project_editor_page.py`'s `listWidget_repositories_requirements` (see
  "UI rewrite (2026-08-19)" above) to show/grayscale a selected repo's own
  direct pipeline dependencies.
- `custom_paths_settings_page.py` — **removed 2026-09-01, see "Settings
  tabs merged into one" below** — its `CustomPathsSettingsPage` class and
  its own `ConnectInputPathDialog`/`CustomPathEditDialog` were folded into
  `project_editor_settings_page.py`/`dialogs.py` respectively; only the
  `.ui` file (`CustomPathWindow.ui`) is gone, the widgets themselves live
  on in `ProjectEditorSettingsWindow.ui`'s "Custom Paths" tab. Kept below
  for the field-level history, which is otherwise unchanged. Used to be: a
  `CATEGORY_PROJECT` Settings tab ("Custom Paths", moved here from
  `CATEGORY_REPO` 2026-09-01, per the user's own request to group it under
  the "Project" header instead of "Repository" — a registration-only
  change in `plugin.py`, the page's own internals are untouched and still
  resolve the *active* repo, not a picked one), split into two
  `QGroupBox` sections. "Create Input Path" — add/rename/edit-path/remove
  the active repo's own `CustomPath` catalog (mostly unchanged logic from
  before 2026-07-19, just relabeled, plus a "Browse..." button added
  2026-07-19 next to the add-row's path field — opens
  `QFileDialog.getExistingDirectory` rooted at the active repo's own
  folder and fills in the chosen folder's path relative to it, rejecting
  anything picked from outside the repo since `CustomPath.path` is always
  relative to it). "Connect Input Path" — the active repo's own outgoing
  pipeline connections, moved here 2026-07-19 from the graph node's
  right-click menu: a list of its current `RepoRef`s, each described with
  an arrow glyph and "(Input)"/"(Output)" matching its `direction` (see
  below) plus Edit and Remove buttons — there was previously no way to
  change or remove a connection at all, since graph edges are
  non-interactive — plus a "Connect..." button opening
  `ConnectInputPathDialog` (defined in this same file) — one compact
  window with a repo `QComboBox`, a custom-path `QComboBox`, and an
  Input/Output direction radio-button pair (added 2026-07-19 — see
  `RepoRef.direction`), together replacing the old two-dialog
  `RepoPickerDialog` + `CustomPathPickerDialog` flow. Edit reopens this
  same dialog pre-filled via its `initial_ref` param (also 2026-07-19),
  shared with "Connect..." through `CustomPathsSettingsPage._run_connect_dialog`.
  A target
  repo with zero declared custom paths shows an inline hint instead of a
  separate `QMessageBox` interruption. Same self-resolving-active-repo
  `refresh()` pattern `interface.md`'s `shared/` `base_repo_settings_page.py`
  entry describes, even though it's `CATEGORY_PROJECT` now — it renders
  under Settings > Project's own header row like `project_database_page.py`/
  `repo_settings_page.py`, not the Repo Setting (Dev) top tab it used to
  share with other `CATEGORY_REPO` plugin tabs (see the bullet above for
  why the move is cosmetic-only). A repo with zero entries in "Create Input Path" can't
  be connected to via "Connect Input Path" at all — this tab is where a
  studio admin has to go first before another repo can reference it.

## Settings tabs merged into one (2026-09-01)

The three separate `CATEGORY_PROJECT` Settings tabs described above
(`CustomPathsSettingsPage`/`custom_paths_settings_page.py`,
`ProjectDatabasePage`/`project_database_page.py`,
`RepoSettingsPage`/`repo_settings_page.py` — each loading its own `.ui`
file, `CustomPathWindow.ui`/`ProjectDatabaseWindow.ui`/`RepoSettingsWindow.ui`)
were merged into **one** Settings tab, per the user's own request after
they hand-merged the three `.ui` files themselves into a single
`ProjectEditorSettingsWindow.ui` — one `Form` with a `QTabWidget` holding
four sub-tabs. All three old files, and their `.ui` files, were deleted;
every widget they used to `findChild` keeps the exact same `objectName` in
the merged file, so the widget-level logic documented above is otherwise
unchanged — only the file layout, class boundary, and Settings
registration collapsed from three to one.

- `project_editor_settings_page.py` — `ProjectEditorSettingsPage`: the one
  remaining Settings tab (key `project_editor_settings`, label "Project
  Editor Settings", order 15, `CATEGORY_PROJECT`), loading
  `ProjectEditorSettingsWindow.ui` via the same `QUiLoader` pattern this
  plugin already used for `ProjectEditorTabWindows.ui`. Its `QTabWidget`'s
  four sub-tabs, and which old page each came from:
  - **"Repo Database"** — Repositories Database
    (`tableWidget_project_repositories_database`), one of
    `ProjectDatabasePage`'s three former `QGroupBox`es.
  - **"Program and External Plugin Database"** — External Plugins Database
    (`tableWidget_external_plugin_database`) and Program Database
    (`tableWidget_project_program_database`), the other two of
    `ProjectDatabasePage`'s former groupboxes. Split across two sub-tabs
    here purely because that's how the user laid out the merged `.ui` —
    not a scope or behavior change from the old single "Project Database"
    tab.
  - **"Repo Enable Plugins and Programs"** — all of former
    `RepoSettingsPage`: the Repositories picker
    (`tableWidget_repositories`), Enable Programs
    (`groupBox`/a `RequirementsTreeWidget` swapped in for the `.ui`'s
    placeholder table), Enable Plugins
    (`tableWidget_external_enable_plugins`).
  - **"Custom Paths"** — all of former `CustomPathsSettingsPage`: Connected
    Custom Path (`tableWidget_connected_custom_path`) and Create This Repo
    Custom Path (`tableWidget_currrent_repo_custom_path`).
  One notable behavior change: `CustomPathsSettingsPage` used to swap an
  `empty_label`/`content_widget` pair to show "Select a repo to see this
  information" when no repo was active — `ProjectEditorSettingsWindow.ui`
  has no such label widget, so the merged page just leaves the "Custom
  Paths" tab's two tables empty (and its Add button a no-op) instead, with
  no plan to add the empty-state message back unless requested.
  Since the three old classes' attribute/method names collided in a few
  places once merged into one class (all three had a `refresh()`; both
  `ProjectDatabasePage` and `RepoSettingsPage` had their own
  `self._repo_ids`/`_selected_repo_id`-shaped state for two conceptually
  different repo tables), the "Repo Database" tab's repo-picker state was
  renamed with a `_database_` infix (`_repo_database_ids`,
  `_selected_database_repo_id()`, `_refresh_repo_database()`) and the
  "Repo Enable Plugins and Programs" tab's kept its original names
  (`_enable_repo_ids`, `self._selected_repo_id`, `_reload_repo_table()`) —
  the "Custom Paths" tab's own state (`_project_id`/`_repo_id`/
  `_custom_paths`/`_connections`) never collided with either and is
  unchanged. `self._plugin_by_id` (full discovered-plugin catalog, keyed by
  id) was identical in both `ProjectDatabasePage` and `RepoSettingsPage`,
  so it's built once and shared by both tabs' logic now, instead of twice.
- `dialogs.py`'s `ConnectInputPathDialog`/`CustomPathEditDialog` — moved
  here from `custom_paths_settings_page.py` in the same change (see that
  file's own bullet above and `dialogs.py`'s bullet near the top of this
  doc).

## Reading pipeline data from another plugin

As of the `Repo.plugin_data` consolidation, this data lives in each repo's
own `plugin_data["project_editor"]` entry (`core/models.py`'s `Repo`),
inside that repo's project blob (`data/projects/<project_id>.json`) — not
in a separate `PluginConfigStore` file anymore. Read it via
`api.metadata.get_repo_plugin_data(project_id, repo_id, "project_editor")`
(same "agree on the `plugin_id` string, don't import this folder"
convention as before, just backed by `MetadataStore` now instead of a
standalone blob). Since a `RepoRef.custom_path_id` is only meaningful
against the **target** repo's own `custom_paths` entry, resolving a
pipeline connection all the way to an actual filesystem path takes two
lookups, not one:

```python
def resolve_pipeline_connection(api, project_id: str, repo_id: str, connection_index: int = 0):
    entry = api.metadata.get_repo_plugin_data(project_id, repo_id, "project_editor")
    connections = entry.get("pipeline_inputs", [])
    if connection_index >= len(connections):
        return None
    ref = connections[connection_index]

    target_entry = api.metadata.get_repo_plugin_data(ref["project_id"], ref["repo_id"], "project_editor")
    custom_path = next(
        (cp for cp in target_entry.get("custom_paths", []) if cp["id"] == ref.get("custom_path_id")), None
    )
    if custom_path is None:
        return None

    target_repo = api.metadata.get_repo(ref["project_id"], ref["repo_id"])
    target_repo_path = Path(api.local_config.workspace_root) / target_repo.local_path
    return target_repo_path / custom_path["path"]
```

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive, or touches `plugin_api/registries/section_registry.py`'s
`UICommandService` (the `open_settings_tab`/`set_active_repo` fields this
plugin's `_wire` binds — `switch_project` used to be a third, bound to the
now-removed `project_settings_page.py`'s "Switch Project..." button; the
`_wire` binding was removed 2026-09-01 along with that file, though the
`UICommandService.switch_project` field itself is framework-level and
wasn't touched). `plugin_api/registries/settings_tab_registry.py`'s
`CATEGORY_PROJECT` and `interface/settings/settings_view.py`'s category
grouping are the one other cross-boundary exception (added 2026-08-03
specifically to give this plugin's Project-scoped Settings tabs — now
`project_database_page.py`/`repo_settings_page.py`/
`custom_paths_settings_page.py` — a real "Project" header row in the
app-level Setting popup) — a genuinely new settings category is
framework-level, not something this plugin's own folder can add by itself.
