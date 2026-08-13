# interface/ reference

Structure/orientation reference for `app/interface/` — PySide6 GUI layer,
builds on `core_api/` (never `core/` directly — see `core-api.md`) for all
data/git operations. Consolidated here (2026-08-13) from `interface/`'s
own former per-folder `README.md`s, which were removed — see root
`CLAUDE.md`'s "Reading this codebase" section for why. Read this before
opening `interface/` speculatively just to get oriented; still open the
actual source once you know which file you need.

**`interface/` is closed** — nothing outside `interface/` itself and
`app/interface_api/` may import `interface.*` directly (enforced by
`developer/app/check_import_boundaries.py`). `launcher.py` and
`plugin_api/__init__.py` reach `MainWindow`/theme helpers/shared widgets
via `interface_api` instead — see [`interface-api.md`](interface-api.md)
for that facade's full re-export surface. This doc stays scoped to what's
*inside* `interface/`.

Organized by domain rather than by suffix convention: each of `sidebar/`,
`repo_settings/`, `settings/` owns one feature area end-to-end (page + its
dialogs + its workers). Explorer and Submit used to live here too
(`explorer/`, `submit/`) but are now real always-on plugins under
`plugins/core/explorer/` and `plugins/core/submit/` — registered into
`SectionRegistry` via `register(api)` exactly like any other plugin, not
special-cased by `interface/` — see `plugins-guide.md` and
`developer/app/docs/plugins/` for how plugin discovery/each plugin works.
`shared/` holds the handful of files genuinely used by 2+ consumers,
`interface/` domains and plugins alike. Everything left flat at the root
is app-wiring with no single domain home — `main_window.py` is the one
file that threads all of it together.

## Root-level app shell (no single window)

- `main_window.py` — top-level `QMainWindow`: constructs every window's
  page from `SectionRegistry` (via `plugin_api`), wires `sidebar/`'s
  `Sidebar` (left-hand navigation column — display-only repo
  thumbnail/name label, `SectionTabList`, a
  `SidebarFooterActionRegistry`-driven footer), and drives active-repo
  restore + auto-sync on launch. GitHub login happens entirely before this
  process is even spawned (see "GitHub login" below), so `MainWindow`
  builds the real UI immediately on construction — no gate to show/teardown.
  Every section (Explorer/Submit/About/Project Editor) is its own
  standalone page in `view_stack`, switched to via `Sidebar.navigation_changed`.
- `page_protocols.py` — `SetRepoPage`/`PathFocusablePage`/`AutoSyncPage`:
  small `@runtime_checkable Protocol`s a page can optionally satisfy
  (structurally — no inheritance needed) so `main_window.py`'s three
  per-page optional-capability call sites use `isinstance()` instead of
  `getattr(page, "...", None)` duck-typing. Each stays independently
  optional on purpose — a single combined Protocol, or a mandatory one,
  would break existing pages.
- `theme.py` — color palette only (`ThemeColors`, `THEMES`,
  `DEFAULT_THEME_NAME`) for the handful of custom `QPainter`-drawn widgets
  and direct `QColor`/`QPalette` call sites (e.g.
  `plugins/core/project_editor/project_graph_view.py`'s graph node/edge
  painting) that need to stay visually consistent with the app's dark
  theme. No stylesheet generation lives here anymore — see the Zero QSS
  Policy below. `core/storage/config_store.py`'s `LocalConfigStore` still
  needs a default theme name to persist, so it keeps its own duplicated
  `DEFAULT_THEME_NAME` literal rather than importing this module (`core/`
  never depends on `interface/`).
- `theme_apply.py` — calls `qdarktheme.setup_theme("dark")`
  (`pyqtdarktheme-fork` on PyPI) once on the `QApplication`; used only by
  `launcher.py`, before the `ProjectSelectorDialog` gate. `theme_name` is
  still accepted as a parameter for call-site/persisted-config
  compatibility but no longer selects anything (`THEMES` only ever had the
  one dark entry).

### Zero QSS Policy (2026-08-13 migration)

`interface/`, `interface_api/`, and `plugins/` no longer call
`setStyleSheet()` or load any `.qss` file, anywhere — the app's entire
visual theme comes from `qdarktheme.setup_theme("dark")` (see
`theme_apply.py` above) plus each widget's own `QPalette`/`QFont`/`QIcon`
calls. Do not reintroduce a custom stylesheet string:
- Text color/weight (the old `[secondary="true"]`/`[cardTitle="true"]`/
  `font-weight: bold` QSS rules) → `interface/shared/widget_helpers.py`'s
  `set_secondary_text(label)`/`set_bold(label)` helpers (re-exported
  through `interface_api`/`plugin_api`), or a direct `QPalette`/`QFont`
  call for anything those two don't cover.
- Status/semantic icons (git dirty/fresh, linked/not-linked, cloned/not
  cloned — the old `[status="..."]`/`[linkStatus="..."]` QSS rules and
  bundled-PNG badges) → `self.style().standardIcon(QStyle.SP_...)` (see
  `plugins/core/submit/status_dot.py`, `plugins/core/software_linker/plugin.py`'s
  `_ProgramLinkCard.refresh`, and
  `plugins/core/project_editor/project_graph_view.py`'s
  `_clone_status_icon` for the pattern — `QGraphicsItem.paint()` has no
  widget of its own, so that last one draws from `QApplication.style()`
  instead of `self.style()`).
- Section-list icons (`SectionSpec.icon_path`/`SectionSpec.standard_icon`
  in `plugin_api/registries/section_registry.py`) — `standard_icon`
  (`QStyle.StandardPixmap`) is what every built-in section uses now;
  `icon_path` (a real bundled bitmap `Path`) is kept available only for a
  future plugin that genuinely needs a custom bitmap (e.g. a brand logo),
  and wins if both are set.
- Card/frame visuals (border-radius, padding, hover backgrounds) that the
  old `build_stylesheet()` used to control for `#requirementCard`,
  `#commitCard`, `#videoCard`, etc. are *not* replicated — `QPalette`/
  `QFont` can't express border-radius or padding, and the user-facing
  design decision (2026-08-13) was to accept qdarktheme's own flat default
  look for these rather than hand-roll custom `paintEvent()`s per widget.
- User-uploaded content images (program icons, repo thumbnails) are
  unaffected by this policy — those stay plain `QPixmap(path)` loads, since
  they're distinguishing content, not status indicators, and no
  `QStyle.StandardPixmap` could stand in for them.
- `builtin_settings_tabs.py` — constructs the built-in Settings tabs
  (pulling from `settings/`, `repo_settings/` — Explorer and Submit
  register themselves from `plugins/core/`, not from here) and registers
  them into `plugin_api`'s `SettingsTabRegistry`, exactly as a plugin would
  register its own.
- `project_selector_dialog.py` — `ProjectSelectorDialog`: the mandatory
  pre-`MainWindow` gate for which Project this run is scoped to, shown by
  `launcher.py` (only when `LocalConfigStore.active_project_id` doesn't
  already resolve and there's more than one project to choose from). Once
  chosen, Project is fixed for the whole run — no page anywhere else can
  change it again; only a real restart back through this same gate can
  (`plugins/core/project_editor`'s Settings > Project "Switch Project...",
  `MainWindow._request_switch_project`).

Note: `section_registry.py`/`settings_tab_registry.py`/
`sidebar_footer_action_registry.py`/`registry_base.py`/
`ui_registry_manager.py`/`program_launch_registry.py` used to live at this
root level too — moved to `app/plugin_api/registries/` (2026-08-13
refactor, see `core-api.md`/`plugin-api.md`) since `PluginAPI` already
owned them and a plugin needs their spec types to register anything.
`interface/` now imports these from `plugin_api`, not the reverse.

## Domain folders

### `sidebar/` — left navigation column

Replaced the old horizontal top `MenuBar` row. A plain widget column (repo
identity, section tab list, sync progress), not Qt's `QMenuBar`.

- `sidebar.py` — `Sidebar`: top to bottom — `ActiveRepoWidget` (thumbnail +
  name label, display-only), `SectionTabList` (stretched to fill remaining
  height), then a footer strip holding sync status and one widget per
  `plugin_api.SidebarFooterActionRegistry` entry (built via
  `spec.widget_factory()`; nothing hardcoded — `Sidebar` just renders
  whatever's registered), then an account row: `account_label`
  (display-only GitHub username, pushed by `MainWindow._start_app`) plus
  the icon-only `setting_button` (the only hardcoded app-level control
  here — not a `SectionTabList` row, since it's app-level not repo-scoped).
  Fixed width (`SIDEBAR_WIDTH`).
- `active_repo_widget.py` — `ActiveRepoWidget`: thumbnail banner
  (fill-cropped, never rounded) + a plain name label. Display-only — no
  click-to-open-picker; the active repo is switched exclusively by
  clicking a node in Project Editor's graph panel
  (`plugins/core/project_editor/`). `MainWindow` pushes into it directly
  (`set_active_labels`/`set_thumbnail`).
- `section_tab_list.py` — `SectionTabList`: a vertical `QListWidget`, one
  row per registered `SectionRegistry` section. Emits
  `navigation_changed(key)` for every row.

**Working here:** stay inside this folder unless the change needs a new
`core_api`/`plugin_api` primitive, or touches `main_window.py`'s wiring
(which constructs `Sidebar` and connects its signals).

### `repo_settings/` — the repo-configuration domain

Settings tabs that manage one specific per-repo concern, split out from
`settings/`'s app/machine-level tabs. Both tabs here are `CATEGORY_REPO`
(registered in `interface/builtin_settings_tabs.py`) and render inside
`interface/settings/settings_view.py`'s **Repo Setting (Dev)** top tab
(see "Rendering history" under `settings/` below). Both subclass
`interface/shared/base_repo_settings_page.py`'s `BaseRepoSettingsPage`,
which resolves the active project/repo itself from `local_config_store` on
`refresh()` and calls each page's own `_on_refresh_content()` override.

- `local_repository_page.py` — `LocalRepositoryPage`: shows the active
  repo's local clone status/path and a "Remove Local Repositories" button
  that `shutil.rmtree`s the clone folder (`core/vcs/paths.py`'s
  `resolve_repo_path`) and marks the repo `not_cloned`
  (`MetadataStore.mark_status`) — does not touch the registry record
  itself, only the on-disk clone.
- `requirements_and_plugins_page.py` — `RequirementsAndPluginsPage`: two
  stacked sections inside a scroll area — **Program Requirements** (embeds
  `interface/shared/requirements_tree_widget.py`'s `RequirementsTreeWidget`,
  editing an *existing* repo's `required_program_ids`/`program_version_pins`)
  and **Enable Plugin** — every discovered plugin, split by
  `core/extensibility/loader.py`'s `plugin_source()` into **Core**
  (`plugins/core/`, always on, no opt-out) and **External**
  (`cache/plugins/`, opt-in via `Repo.required_plugin_ids`). (Un)checking
  an External plugin flips its sidebar section's visibility for this repo
  (`interface/main_window.py`'s `_apply_plugin_visibility`). A
  project-selected entry not yet cloned shows as its own checkable row —
  checking it clones it immediately via `GitService` and marks it required
  by reading the fresh clone's `manifest.json`; still needs a restart to
  actually load (plugin discovery is one-shot at app startup).

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive, a `shared/` addition, or touches
`interface/settings/settings_view.py` (the container that renders these
tabs) or `interface/main_window.py`'s `_apply_plugin_visibility`.

### `settings/` — app/machine-level Setting tabs

The "Setting" popup — opened via the icon-only Setting button in Sidebar's
footer. Every `SettingsTabSpec` page **self-persists on every change** —
no Save/Cancel step. Cloud sync has no settings window at all anymore — a
single shared R2 key is baked into `UkoreHubLauncher.exe` (see the
`ukorehub-cloud-sync` skill), no per-artist config.

- `settings_view.py` — `SettingsView` (a top-level `QTabWidget`, three
  categories) + `SettingsDialog` (the popup wrapper).
  `MainWindow._on_settings_requested` constructs a fresh `SettingsDialog`
  on every open — no state carried between opens. Driven by
  `plugin_api.SettingsTabRegistry` (open, ordered — built-in and
  plugin-provided tabs register into the same collection). Renders three
  top-level tabs: **Account** (`CATEGORY_GENERAL`), **Project (Dev)**
  (`CATEGORY_PROJECT` + `CATEGORY_DEVELOPER`), **Repo Setting (Dev)**
  (`CATEGORY_REPO`). `get_tab_widget(key)` is the public escape hatch for
  reaching a specific constructed page from outside — `main_window.py`
  uses it to connect `CommonSettingsPage.logout_requested`.
- `common_settings_page.py` — account info (avatar, GitHub username, login
  date), workspace folder (read-only), Logout button (clears cached
  token/username/login-date via `core_api`'s `SecureTokenStore` and
  relaunches `UkoreHub.exe`), Restart button (`os.execv` re-exec).
  `CATEGORY_GENERAL`.
- `github_oauth_settings_page.py` — `GithubOAuthSettingsPage`: just the
  GitHub OAuth Client ID field — studio-admin plumbing, still needed since
  the launcher's own login step reads this same `data/system_config.json`
  value. `CATEGORY_DEVELOPER`.
- `program_database_page.py` — `ProgramDatabasePage`: CRUD for the active
  Project's own Program Database (`core/models.py`'s `Project.programs`,
  via `core_api`'s `MetadataStore` — each Project has its own, not
  shared). Reads `local_config_store.active_project_id` directly. Uses
  `program_dialog.py`'s `ProgramDialog` for add/edit. `CATEGORY_PROJECT`.
- `program_dialog.py` — `ProgramDialog`: name/version/description/icon
  editor for one `Program`, used only by `program_database_page.py`.
- `plugin_catalog_page.py` — read-only listing of what got discovered
  under `plugins/`. `CATEGORY_DEVELOPER`.

**Rendering history:** from 2026-07-15 through the 2026-07-20 refactor,
`SettingsView` didn't render `CATEGORY_REPO` at all — every such tab
rendered instead inside `plugins/core/project_editor/`'s "Repository
Setting" popup (now retired). `CATEGORY_REPO` tabs render here again,
under **Repo Setting (Dev)**, and a repo node's "Repository Setting..."
right-click opens this same dialog (`UICommandService.open_settings_tab`)
instead of a popup — see `plugins/core/project_editor/project_graph_view.py`'s
`open_repo_settings()`.

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive, a `shared/` addition, or touches `main_window.py`'s
wiring (which opens `SettingsDialog` via `Sidebar.settings_requested`).

### `shared/` — multi-consumer widgets/helpers

Every file here has a confirmed 2+ consumer (`interface/` domains and
plugins alike) — a file with only one real consumer moves into that
consumer's own folder instead.

- `base_repo_settings_page.py` — `BaseRepoSettingsPage`: shared base for a
  Settings tab scoped to a single repo (the `empty_label`/`content_widget`
  scaffolding + `refresh()` preamble). A subclass adds its own layout onto
  `content_widget` and overrides `_on_refresh_content()`.
- `requirements_tree_widget.py` — `RequirementsTreeWidget`: each Program is
  a checkable top-level node, with a checkable child per version for a
  multi-version Program (pin, radio-style). Used by
  `plugins/core/project_editor/dialogs.py`'s `RepoDialog` (repo creation,
  via `plugin_api`) and `interface/repo_settings/requirements_and_plugins_page.py`
  (editing an existing repo's requirements, direct in-`interface/` import).
- `commit_history.py` — `CommitCard` widget, `CommitFilesDialog` (the
  "Files changed" popup, public since 2026-08-13 so a caller can open it
  without going through a `CommitCard`), `CommitHistoryEntry`,
  `format_commit_date`, `format_relative_time` ("3 hours ago" — Submit's
  table only, `format_commit_date` is the absolute-date one both callers
  use), `fetch_entries_via_github` (GitHub-API-first, local-git-fallback).
  Used by `plugins/core/explorer/`'s per-path commit panel (plain
  `CommitCard`s) and `plugins/core/submit/`'s whole-repo commit history
  panel (a plain `QTableWidget`, double-click a row to open
  `CommitFilesDialog` directly) — both via `plugin_api`.
- `image_asset.py` — `pick_image_file` (the `QFileDialog.getOpenFileName`
  wrapper every icon/thumbnail chooser uses) and `save_image_asset` (copy
  the chosen file into an `assets/*_icons`/`assets/thumbnails`-style dir).
  Used by `plugins/core/project_editor/`'s node context menu (via
  `plugin_api`) and `settings/program_dialog.py`/`program_database_page.py`
  (direct in-`interface/` import).
- `widget_helpers.py` — `wrap_scrollable` (the `QScrollArea(widgetResizable)`
  wrapper every scrollable tab/panel builds by hand), `confirm_action`
  (the Yes/No-defaulting-to-No `QMessageBox.warning` every delete/revert
  confirmation uses), `show_exclusive` (the empty-state/content-state
  visibility toggle every page's `set_repo()` does).

**Working here:** a change to a file in this folder affects every consumer
listed above for it — check all of them, not just the one that sent you
here. Every symbol here is also re-exported through `interface_api`
(`launcher.py`) and `plugin_api` (`plugins/`) — renaming or changing a
signature means updating those re-exports too, not just this folder.

## GitHub login

There is no login domain in `interface/` anymore. GitHub login (OAuth
device flow) and the token cache live in `updater.py` (`UkoreHubLauncher`
repo), run by the launcher exe (`UkoreHub.exe`) *before* this process is
even spawned — by the time `launcher.py` constructs `GitService`, it just
loads whatever token the launcher already cached and calls
`git_service.set_github_token(...)`.

`MainWindow` still shows the signed-in username (`Sidebar.account_label`)
and still owns logout (`Settings > Common`'s Logout button) — but logout
here doesn't tear down any in-app UI: it clears the cached token/username
via `SecureTokenStore` and relaunches `UkoreHub.exe`, whose own login step
shows the GitHub login screen again.

## Testing conventions

Qt widgets are **never constructed inside pytest tests**: registries are
tested with `page_factory=lambda: None`, verifying registry bookkeeping
only, never `QWidget` behavior. For anything that genuinely needs a live
`QApplication` + `MainWindow`, use a throwaway headless smoke-test script
instead (see root `CLAUDE.md`'s "Headless/smoke testing" section — always
a scratch copy of `data`/`cache`, never the real ones): construct
`QApplication`, all registries, and `MainWindow` without calling
`app.exec()`. End the script with `sys.stdout.flush(); os._exit(0)` —
`os._exit` is required because Qt/Windows can hang on normal process
teardown after `QApplication` is destroyed without an explicit
`app.quit()`.
