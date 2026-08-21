# plugin_api reference

Complete command reference for `app/plugin_api/` — the only import surface
`app/plugins/core/<Name>/` code may use. Read this instead of opening
`app/plugin_api/` directly; see root `CLAUDE.md`'s rule on this (reading
that folder itself requires the user's explicit permission — an `ask`
permission rule in `.claude/settings.json`). Only open the real source if
something you need genuinely isn't covered here — then update this doc
with what you found, so the next session doesn't need to open it either.

## Where this sits

```
core/          [CLOSED] non-UI logic — MetadataStore, GitService, models,
               exceptions, ... Nothing outside core/ and plugin_api/ may
               import core.* directly.
interface/     [CLOSED] PySide6 GUI shell — shared widgets, theme, ...
               Nothing outside interface/ and interface_api/ may import
               interface.* directly.
interface_api/ [FACADE] the only thing allowed to reach into interface/ —
               see interface-api.md.
plugin_api/    [FACADE] the only thing allowed to reach into core/ or
               interface/ from plugins/ — re-exports core/ types (via
               core_api) and interface/ UI symbols (via interface_api).
               Also owns the Qt-aware UI registries (SectionRegistry, ...)
               — moved here from interface/ because PluginAPI already
               composed them, and a plugin needs their spec types
               (SectionSpec, ...) to call api.register_section() at all.
interface/     the main app shell — imports registries FROM plugin_api/.
plugins/       core/<Name>/ plugin folders — import ONLY from plugin_api/
               (plus PySide6/stdlib/third-party) — never core.* or
               interface.* directly.
```

A plugin file should never write `from core.xxx import yyy` or
`from interface.xxx import yyy`. Write `from plugin_api import yyy`
instead. If something you need isn't re-exported yet, that's a real gap —
add the re-export to `plugin_api/__init__.py` (not a direct `core.*`/
`interface.*` import in your plugin file — if it's a `core/` type, source
it from `core_api`; if it's an `interface/` UI symbol, source it from
`interface_api`, adding the re-export there first if needed too), then add
it to this doc.

## Quick start — `register(api)`

Every plugin's `entry_point` (conventionally `plugin.py`) needs exactly
one function, called once at app startup with no guaranteed order between
plugins:

```python
from plugin_api import SectionSpec

def register(api) -> None:
    api.register_section(SectionSpec(
        key="my_plugin",
        label="My Plugin",
        order=50,
        page_factory=lambda: MyPluginPage(api),
    ))
```

`api` is a single shared `PluginAPI` instance (`plugin_api/plugin_api.py`)
— the same one every plugin's `register(api)` receives. See
`app/plugins/README.md` for the full plugin-authoring guide (manifest.json
shape, multi-file import conventions, cross-plugin data sharing); this doc
is scoped to *what plugin_api exposes*, not how to write a plugin end to
end.

## `PluginAPI` — properties

| Property | Type | Notes |
|---|---|---|
| `api.metadata` | `MetadataStore` | The Project/Repo registry. Also owns Program CRUD (`list_programs(project_id)`, `get_program(project_id, id)`, ...) — `.get_program(...)` raises `plugin_api.NotFoundError`, not `None`/`KeyError`. The sanctioned way to write to the registry. |
| `api.local_config` | `LocalConfigStore` | Per-machine settings (workspace root, theme, active project/repo, GitHub username). |
| `api.git` | `GitService` | Git subprocess wrapper (clone/pull/push/commit/status/log/...). The sanctioned way to run a git operation — typically from a background `QThread`. Includes `force_sync(repo_path)` — fetch + `reset --hard origin/<branch>` + `clean -fd`, discarding all local changes/unpushed commits and clearing any in-progress merge; never confirms with the user itself, added for `ExternalPluginManager`'s "Force Update Selected". |
| `api.repo_context` | `RepoContextDTO \| None` | Read-only snapshot of the active project/repo (id/name, resolved repo path, `workspace_root`, `required_plugin_ids`). `None` if no repo is active yet. **Does not replace** `api.metadata`/`api.git` for writes or git operations — a frozen DTO architecturally can't cover those. |
| `api.plugin_catalog` | `list[DiscoveredPlugin]` | Every plugin `discover_plugins()` loaded this launch (Core and repo/`cache/plugins` alike). For resolving another plugin's id to its manifest (name, `requires`, ...). |
| `api.system_config_store` | `SystemConfigStore` | Shared, cloud-synced studio config (e.g. `r2_bucket_name`, `github_client_id`). |
| `api.cache_dir` | `Path` | UkoreHub's per-machine `cache/` directory (gitignored) — for a plugin building its own per-machine state. |
| `api.cloud_sync` | `R2JsonSync \| None` | The already-built cloud-sync engine, or `None` if not configured/reachable this run. Read-only access — don't import `R2JsonSync` yourself (see "What's deliberately not re-exported" below). |
| `api.debug_log_handler` | `QtLogHandler \| None` | DebugConsole-only plumbing — the shared `interface_api.QtLogHandler` its page reads/subscribes to, or `None` if unwired (e.g. a bare test construction). **Don't use this for general logging** — any plugin just calls `logging.getLogger("YourPlugin").info(...)`/`.warning(...)` etc. directly, no `api` involved at all, and it shows up live in DebugConsole automatically. See `developer/app/docs/plugins/DebugConsole.md`. |
| `api.file_opener_registry` | `FileOpenerRegistry` | Read access to the registry `register_file_opener()` writes into — for a page that needs to call `.find_opener()` itself (e.g. Explorer). |
| `api.program_launch_registry` | `ProgramLaunchRegistry` | Read access to the registry `register_program_launcher()` writes into — `software_linker`'s Program Launcher tab uses this to look up a plugin-contributed launch behavior for a given Program. |
| `api.settings_tab_registry` | `SettingsTabRegistry` | Read access to the registry `register_settings_tab()` writes into — for a page that needs to enumerate every `CATEGORY_REPO` tab generically (e.g. `project_editor`'s right panel). |
| `api.app_root` | `Path` | UkoreHub's own install root — for referencing other paths inside the install without guessing nesting depth from `__file__`. |

## `PluginAPI` — registration methods

| Method | Signature | Notes |
|---|---|---|
| `register_section` | `(spec: SectionSpec) -> None` | Adds a full top-level sidebar section/tab. |
| `register_settings_tab` | `(spec: SettingsTabSpec) -> None` | Adds a tab inside the Setting dialog. |
| `register_file_opener` | `(plugin_id: str, extensions: list[str], opener: Callable[[Path, Repo], bool]) -> None` | Claims responsibility for opening certain file extensions from Repo Browser. |
| `register_program_launcher` | `(spec: ProgramLaunchSpec) -> None` | Contributes custom launch behavior for a Program (e.g. Maya's setProject/env-merge wiring) instead of a bare `subprocess.Popen`. |
| `register_sidebar_footer_action` | `(spec: SidebarFooterActionSpec) -> None` | Adds a widget to Sidebar's footer strip. |

## `PluginAPI` — lifecycle hooks

| Method | Fires |
|---|---|
| `on_app_start(handler)` | Once, right after the app finishes launching. |
| `on_repo_changed(handler)` | Every time the user switches the active repo. |
| `on_app_close(handler)` | Once, as the main window is closing. |

`handler` is `Callable[[AppLifecycleContext], None]` — `AppLifecycleContext`
has `.project`, `.repo`, `.repo_path`, `.extra`. One broken handler is
isolated and never breaks another plugin's handler for the same event.

## `PluginAPI` — config stores (cross-plugin / cross-machine data)

| Method | Returns | Use for |
|---|---|---|
| `plugin_config_store(plugin_id, *, shared=False)` | `PluginConfigStore` | `shared=False` (default): per-machine, gitignored (`cache/plugin_local_config/`). `shared=True`: studio-wide, cloud-synced via Cloudflare R2 (`data/plugins/core/`). Two plugins agreeing on the same `plugin_id` string share the same file — no import needed. |
| `project_plugin_config_store(plugin_id)` | `ProjectPluginConfigStore \| None` | Same get/set contract, scoped to the currently active Project (`Project.plugin_data`) instead of one studio-wide blob. `None` when no project is active yet — callers must handle this. |

**Project/repo-scoped data** (always keyed by exactly one `(project_id,
repo_id)` pair) belongs on the Repo itself instead:
`api.metadata.get_repo_plugin_data(project_id, repo_id, plugin_id)` /
`set_repo_plugin_data(...)`.

See `app/plugins/README.md`'s "Sharing data with another plugin" section
for the full worked examples and when to reach for each option.

## Registry spec dataclasses (what you pass to the `register_*` methods)

- **`SectionSpec`** — `key, label, order, page_factory: Callable[[], QWidget]`, optional `background_threads`, `icon_path` (a real bundled bitmap `Path` — no built-in section uses this anymore, kept for a future plugin that genuinely needs a custom bitmap, e.g. a brand logo), `standard_icon` (`QStyle.StandardPixmap` — what every built-in section's sidebar row icon uses now; `icon_path` wins if both are set), `trailing_widget_factory`, `wire: Callable[[QWidget, UICommandService], None]`.
- **`SettingsTabSpec`** — `key, label, order, page_factory`, optional `on_activated: Callable[[QWidget], None]`, `category` (one of `CATEGORY_GENERAL` (default), `CATEGORY_PROJECT`, `CATEGORY_REPO`, `CATEGORY_DEVELOPER`).
- **`SidebarFooterActionSpec`** — `key, order, widget_factory: Callable[[], QWidget]`, optional `background_threads`.
- **`ProgramLaunchSpec`** — `match: Callable[[Program], bool]`, `launch: Callable[[Repo], bool]`. First match wins, in registration order.
- **`UICommandService`** — passed to `SectionSpec.wire(page, host)`: `set_status_message`, `navigate_and_focus`, `set_active_repo`, `open_settings_tab`, `switch_project`, `refresh_section` — named callbacks a plugin page calls into without holding a `MainWindow` reference. `refresh_section(key)` asks another section to re-read its own on-disk/data state (calls that page's optional `refresh_content()` method if it has one) without switching the visible tab — e.g. Submit's Sync button telling Explorer to rescan after a clone/pull, since Explorer's `QFileSystemModel` watcher can miss/lag a bulk filesystem change.

All four `*Registry` classes (`SectionRegistry`, `SettingsTabRegistry`,
`SidebarFooterActionRegistry`, `ProgramLaunchRegistry`) and
`UIRegistryManager` (bundles all of them + `FileOpenerRegistry`) are also
importable directly from `plugin_api` — a plugin almost never constructs
these itself (that's `launcher.py`'s job), only the spec dataclasses above.

## Re-exported `core/` types

Everything below is importable as `from plugin_api import X` — never
`from core.xxx import X` in a plugin file.

**Models** (`core/models.py`): `Repo`, `Project`, `Program`, `RepoStatus`
(`.unstaged_changes`/`.staged_changes`: `list[FileChange]` — untracked files
merge into `unstaged_changes` with `change_type="untracked"`), `FileChange`
(`path: str`, `change_type: str` — `"untracked"|"added"|"modified"|
"deleted"|"renamed"`)

**Exceptions** (`core/exceptions.py`): `NotFoundError`, `ConflictError`,
`GitOperationError`, `GitHubAuthError`, `UkoreHubError`, `ValidationError`

**Service types** (for constructor type hints — the actual shared instance
always comes from `api.metadata`/`api.git`/`api.local_config`, never
construct these yourself): `GitService`, `MetadataStore`,
`LocalConfigStore`, `SystemConfigStore`

**Plugin-loader types** (`core/extensibility/loader.py`): `DiscoveredPlugin`,
`PluginManifest`, `plugin_source`

**Config store classes** (`core/extensibility/config_store.py`):
`PluginConfigStore`, `ProjectPluginConfigStore`

**File opener** (`core/extensibility/file_opener.py`): `FileOpenerRegistry`,
`FileOpenerSpec`

**Events** (`core/events/`): `AppLifecycleContext`, `AppLifecycleHandler`

**Logging** (`interface/qt_log_handler.py`, re-exported via
`interface_api`): `QtLogHandler` — DebugConsole-only, see
`api.debug_log_handler` above; general plugin code should use
`logging.getLogger(__name__)` instead.

**Misc helpers**: `check_repo_access` (`core/vcs/repo_access.py`),
`extract_git_repo_name` (`core/vcs/paths.py`), `open_in_file_explorer`,
`open_with_default_app` (`core/os_utils.py`), `relaunch_ukorehub_exe`
(`core/relaunch.py` — `(repo_root: Path) -> bool`; spawns
`UkoreHubLauncher.exe` detached and returns `True`, or returns `False` if
no built exe exists one directory above `repo_root` — pass `api.app_root`.
Added for `ExternalPluginManager`'s Force Update popup, which falls back
to `subprocess.Popen([sys.executable, *sys.argv])` + `QApplication.quit()`
when it returns `False`, same dev-checkout fallback
`interface/main_window.py`'s own `_restart_app` uses — see that plugin's
doc for the full flow)

## Re-exported `interface/` types

Everything below is importable as `from plugin_api import X` — never
`from interface.xxx import X` in a plugin file. Sourced from
`interface_api` (see `interface-api.md`), the only thing besides
`interface/` itself allowed to import `interface.*` directly.

**Shared widgets** (`interface/shared/`): `wrap_scrollable`,
`confirm_action`, `show_exclusive`, `set_secondary_text`, `set_bold`
(`widget_helpers.py` — the last two are the zero-QSS text-styling helpers,
see `interface.md`'s Zero QSS Policy section); `CommitCard`,
`CommitFilesDialog`, `CommitHistoryEntry`, `fetch_entries_via_github`,
`format_commit_date`, `format_relative_time` (`commit_history.py`);
`pick_image_file`, `save_image_asset` (`image_asset.py`);
`RequirementsTreeWidget` (`requirements_tree_widget.py`)

**Theme** (`interface/theme.py`): `DEFAULT_THEME_NAME`, `get_theme` — a
color palette for direct `QPainter`/`QColor` call sites only now, not app
chrome (see `interface-api.md`)

**Misc**: `LOCAL_REPOSITORY` (`interface/builtin_settings_tabs.py` — the
`SettingsTabRegistry` key for the Local Repository tab, used by
`project_editor` to open it from a right-click menu)

## What's deliberately *not* re-exported

`core.vcs.cloud_sync.R2JsonSync` — never import this directly from a
plugin file. Use `api.cloud_sync` (the already-built instance) instead.
This isolation keeps `boto3` out of `UkoreHubLauncher.exe`'s frozen build
(only `launcher.py` and `plugin_api/plugin_api.py` itself import
`cloud_sync` — see `core-api.md`'s "What's deliberately not re-exported"
section, or `core/vcs/cloud_sync.py`'s own module docstring).

## What plugin_api does *not* cover

- **Cross-plugin UI navigation** (`UICommandService.navigate_and_focus`,
  a plain string `SectionRegistry` key) and **cross-plugin data**
  (`plugin_config_store` with a shared `plugin_id` string) — see
  `app/plugins/README.md`'s own sections on these; never import another
  plugin's module directly.
- **How to author a plugin end to end** (manifest.json shape, multi-file
  package layout, testing conventions) — see `app/plugins/README.md`.

## If this doc is missing something

Add the re-export to `app/plugin_api/__init__.py` first (following the
existing pattern — group by source module, add to `__all__`), then add a
row/entry to this doc in the same commit. Don't have a plugin file import
`core.*`/`interface.*` directly as a workaround — that's exactly the
violation `developer/app/check_import_boundaries.py` checks for.
