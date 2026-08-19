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

1. **Project/Repo CRUD** — Add/Rename/Delete Project (Setting > Project,
   moved there 2026-08-03 from the graph view's own top bar — see
   `project_settings_page.py` below), Add/Rename/Delete/Thumbnail Repo
   (node context menu) — same `MetadataStore` calls (`core_api`) the old
   tree page made, just triggered from Settings/graph UI instead of tree
   rows/buttons.
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
  with `wire=_wire` — `_wire` calls `page.bind_set_active_repo(host.set_active_repo)`,
  `page.bind_switch_project(host.switch_project)`, and
  `page.bind_open_settings_tab(host.open_settings_tab)` — all three
  `UICommandService` fields (see `plugin_api/registries/section_registry.py`)
  so a node click can trigger a real active-repo switch, Settings >
  Project's "Switch Project..." button can trigger a full app restart, and
  a node's "Repository Setting..." right-click can open the unified
  Settings dialog on its Repo Setting (Dev) category — all without the
  page holding a `MainWindow` reference.
- `dialogs.py` — `ProjectDialog`/`RepoDialog`/`AssignCategoryDialog` (added
  2026-08-19 — a single `QComboBox` of "(Uncategorized)" + every existing
  `Category` + "New Category..." (reveals a name field), backing a node's
  right-click "Assign to Category..." action; never talks to
  `PipelineStore` itself, just hands the caller back an existing category
  id / `None` / a new name to create, same as `RepoDialog`/`ProjectDialog`
  handing back plain values for their own caller to act on). `RepoDialog`
  embeds
  `interface/shared/requirements_tree_widget.py`'s `RequirementsTreeWidget`
  (the checkable Program requirements tree, for repo creation) — that
  widget briefly lived in this file (moved in 2026-07-20, moved back out
  2026-08-04 once `interface/repo_settings/requirements_and_plugins_page.py`
  became a second real consumer; see `interface.md`'s `shared/` section).
  `ProjectDialog`/`RepoDialog` themselves are imported as a normal sibling
  module (`from plugins.core.project_editor.dialogs import ...`, the same
  real-package convention `plugins-guide.md`'s "Multi-file plugins"
  section documents), not a relative import. Used by
  `project_editor_page.py` (`RepoDialog`, repo list's right-click context
  menu Add/Edit Repo, plus `add_repo` — see below) and
  `project_settings_page.py` (`ProjectDialog`, "Add New Project..."/Rename
  Project — moved here from `project_editor_page.py` 2026-08-03, see that
  file's own bullet).
- `project_editor_page.py` — `ProjectEditorPage`: the section's top-level
  widget. As of 2026-08-19 this loads `ProjectEditorTabWindows.ui` at
  runtime via `QUiLoader` (same pattern `custom_paths_settings_page.py`
  uses for `CustomPathWindow.ui`) instead of building a `QGraphicsView`
  node graph in code — see "UI rewrite (2026-08-19)" below for the full
  shape. `current_project_id()`/`add_repo()` remain this page's own single
  source of truth/entry points — `plugin.py` binds these to
  `ProjectSettingsPage`'s `get_current_project_id`/`add_repo` callbacks, so
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
  selected, selected. `bind_switch_project()`/
  `switch_project()` is the only way to view a different project at all,
  and it does that via a full app restart (`UICommandService.switch_project`,
  wrapping `MainWindow._request_switch_project`), not an in-place load.
  Implements the standard `set_repo()` page protocol purely to keep the
  list's bold active-repo row and the detail panel in sync when the active
  repo changes elsewhere — this page only *reacts* to active-repo changes
  except when the user selects an already-cloned row (see "Selecting a
  row" below).
- `project_settings_page.py` — `ProjectSettingsPage`: a `CATEGORY_PROJECT`
  Settings tab ("Project", added 2026-08-03), rendered by
  `interface/settings/settings_view.py` under its own "PROJECT" header row
  (alongside General/Developer) rather than in the Repository Setting
  popup. Originally had a project `QComboBox` here to view a different
  project's graph in place — **removed** as of the single-project-per-
  session change: Project is fixed for the whole run by `launcher.py`'s
  mandatory Project Selector gate, so this tab now just shows the active
  project's name (read-only), Rename/Delete acting on it, Add Repo, "New
  Project..." (adds to the shared catalog without switching into it — only
  selectable the next time the Selector gate actually runs), and "Switch
  Project..." (the only way to view a different project at all — triggers
  a real app restart back through that gate, `on_switch_project`, bound to
  `ProjectEditorPage.switch_project`). Deleting the currently-active
  project also falls through to the same restart, since there's nothing
  left for this session to show otherwise. Holds no state of its own;
  every read/action goes through the `get_current_project_id`/`add_repo`/
  `on_switch_project` callbacks `plugin.py` binds to
  `ProjectEditorPage.current_project_id`/`add_repo`/`switch_project`.
- `project_graph_view.py` — **removed 2026-08-19**, see "UI rewrite
  (2026-08-19)" below. Used to hold `ProjectGraphView` (`QGraphicsView`),
  `RepoNodeItem`, `PipelineEdgeItem`, and `CategoryBoxItem` — the node
  graph this plugin used from 2026-07-15 through then.
- `required_repo_clone_worker.py` — `RequiredRepoCloneWorker` (`QThread`):
  clones/pulls a fixed list of `(project_id, Repo)` targets sequentially,
  stopping at the first failure (repos already cloned earlier in the same
  batch are left on disk, never rolled back). Used by
  `project_editor_page.py`'s Clone button (a single-element target list —
  see "UI rewrite" below; before 2026-08-19 also used by the now-removed
  `ProjectGraphView.request_active_repo` to clone a repo's direct pipeline
  requirements before switching to it, a cascading-clone behavior the list
  rewrite dropped in favor of the explicit per-repo Clone button plus the
  visible Repositories Requirement list). A deliberate local duplicate of
  `plugins/core/submit/git_stream_worker.py`'s
  QThread-wraps-a-callable/`finished_ok`/`failed` shape rather than an
  import of it — this plugin doesn't reach into a sibling plugin's source
  (see "Working here" at the bottom of this file).
- `repo_status_scan_worker.py` — `RepoStatusScanWorker` (`QThread`): the
  table's Status column background check — see the "Status column" bullet
  below. Continues past a single repo's failure (unlike
  `RequiredRepoCloneWorker` above, which stops at the first one), since
  one repo's git status has no bearing on any other row. Same local-copy
  boundary rule as `required_repo_clone_worker.py`.

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

- **`tableWidget_Repo`** (`QTableWidget`, 3 columns —
  `_COL_NAME`/`_COL_STATUS`/`_COL_CONNECTION`,
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
- **Status column** (`_set_status_cell`, `_STATUS_ICONS`) — a live icon,
  same three states `submit/repo_git_status_page.py`'s sidebar status dot
  uses (`QStyle.SP_MessageBoxWarning` dirty / `SP_DialogApplyButton`
  clean), plus `SP_DialogNoButton` for not-cloned and
  `SP_MessageBoxCritical` if the check itself failed. Not-cloned is known
  synchronously (same `GitService.is_cloned` check as the thumbnail); a
  cloned repo shows `SP_BrowserReload` ("Syncing...") immediately, then a
  background `RepoStatusScanWorker` (`repo_status_scan_worker.py` — a
  local duplicate of `submit/git_stream_worker.py`'s shape, same boundary
  rule `required_repo_clone_worker.py` already follows) runs
  `GitService.get_status` per cloned repo sequentially and flips each row
  to Modified/Up to date (or the critical icon on a per-repo failure) as
  results stream in — non-blocking, no `QProgressDialog`, unlike Clone's
  worker use below. `_status_scan_token` (bumped on every
  `_reload_repo_table()`) lets `_on_status_ready`/`_on_status_failed` drop
  a result from a scan the table has since moved past, without needing to
  cancel the worker thread itself. `_status_workers` is a plain list kept
  only so a running `QThread` isn't garbage-collected out from under
  itself before it finishes — each worker removes itself
  (`_on_scan_finished`) and calls `deleteLater()` when its `scan_finished`
  signal fires.
- **Connection column** (`_refresh_connection_column`) — only lights up
  for a row the currently **active** repo (not the *selected* row) has a
  Custom Paths connection to: reads `PipelineStore.get_inputs(project_id,
  active_repo_id)` and, for each `RepoRef` whose target is a row in this
  table, sets `QStyle.SP_MediaSkipBackward` for an `"input"` connection or
  `SP_MediaSkipForward` for `"output"` — a quick-glance replacement for
  the old graph's directed edges, per the user's own request. Recomputed
  on every `_reload_repo_table()` and, cheaply (no table rebuild), on
  every pure active-repo switch via `set_repo()`.
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
- **Clone / Unclone buttons** — act on whichever repo is currently
  *selected* in the table (`_selected_repo_id`, independent of the active
  repo). Clone (disabled once already cloned) confirms, then runs
  `RequiredRepoCloneWorker` with a single `[(project_id, repo)]` target
  behind a `QProgressDialog` (`_run_clone_worker` — the same
  worker/dialog/`QEventLoop` shape `ProjectGraphView._clone_required_repos`
  used to use for the cascading multi-repo case), then also switches the
  active repo to it. Unclone (disabled while not cloned) confirms, then
  `shutil.rmtree`s `workspace_root / repo.local_path` and calls
  `MetadataStore.mark_status(project_id, repo_id, "not_cloned")` — the
  same status string `interface/repo_settings/local_repository_page.py`'s
  "Remove Local Repositories" button already uses for the same operation,
  just now reachable per-repo from this table too instead of only for the
  currently-active repo.
- **Right-click context menu** on a table row — "Repository Setting...",
  "Rename Repo...", "Change Thumbnail...", "Delete Repo" (no "Assign to
  Category..." entry anymore, see "Second pass" below). "Repository
  Setting..." still opens the unified Settings dialog via
  `bind_open_settings_tab`/`UICommandService.open_settings_tab` for
  whichever repo is currently *active*, not necessarily the row that was
  right-clicked — every `CATEGORY_REPO` tab self-resolves the active repo
  from `local_config_store` regardless.

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
  both there and the app-level Setting dialog at once. Those tabs now
  render inside `interface/settings/settings_view.py`'s Repo Setting (Dev)
  top tab instead — see `interface.md`'s `settings/` "Rendering history"
  note — and `project_editor_page.py`'s `_open_repo_settings()` (formerly
  `ProjectGraphView.open_repo_settings()`, before the 2026-08-19 UI
  rewrite) opens that same dialog via `UICommandService.open_settings_tab`
  rather than building a second one).
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
  round-trip on old data unchanged).
  `get_required_repos(project_id, repo_id)` resolves a repo's own direct
  `pipeline_inputs` refs into the actual target `Repo` objects (deduped,
  direct-only — no recursion into each target's own inputs), used by
  `project_editor_page.py`'s `listWidget_repositories_requirements` (see
  "UI rewrite (2026-08-19)" above) to show/grayscale a selected repo's own
  direct pipeline dependencies.
- `custom_paths_settings_page.py` — `CustomPathsSettingsPage`: a
  `CATEGORY_REPO` Settings tab ("Custom Paths"), split into two
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
  entry describes. Shows up wherever `CATEGORY_REPO` tabs render generically
  (`interface/settings/settings_view.py`'s Repo Setting (Dev) top tab) — no
  wiring needed there. A repo with zero entries in "Create Input Path" can't
  be connected to via "Connect Input Path" at all — this tab is where a
  studio admin has to go first before another repo can reference it.

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
`UICommandService` (the `open_settings_tab`/`set_active_repo`/`switch_project`
fields this plugin's `_wire` binds). `plugin_api/registries/settings_tab_registry.py`'s
`CATEGORY_PROJECT` and `interface/settings/settings_view.py`'s category
grouping are the one other cross-boundary exception (added 2026-08-03
specifically to give `project_settings_page.py` a real "Project" header
row in the app-level Setting popup) — a genuinely new settings category is
framework-level, not something this plugin's own folder can add by itself.
