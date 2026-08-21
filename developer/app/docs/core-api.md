# core_api reference

Complete command reference for `app/core_api/` — the only import surface
`app/interface/`, `app/launcher.py`, and `app/plugin_api/`'s own facade
files (`plugin_api/plugin_api.py`, `plugin_api/registries/*.py`) may use
to reach `app/core/`. Read this instead of opening `app/core_api/`
directly; see root `CLAUDE.md`'s rule on this (reading that folder itself
requires the user's explicit permission — an `ask` permission rule in
`.claude/settings.json`). Only open the real source if something you need
genuinely isn't covered here — then update this doc with what you found,
so the next session doesn't need to open it either.

For `app/plugins/core/<Name>/` plugin code specifically, use
[`plugin-api.md`](plugin-api.md) instead — `plugin_api` re-exports
everything a plugin needs (itself sourced from `core_api`), and a plugin
file should never import `core_api` (or `core`) directly.

## Where this sits

```
core/          [CLOSED] non-UI logic — MetadataStore, GitService, models,
               exceptions, ... Nothing outside core/ and core_api/ may
               import core.* directly.
core_api/      [FACADE] the only thing allowed to reach into core/. Owns
               UkoreCore (core_api/app_core.py) — the composition object
               launcher.py constructs once and threads into MainWindow/
               PluginAPI.
interface/     the main app shell — imports types FROM core_api/.
plugin_api/    the plugins/ facade — its own facade files import types
               FROM core_api/ too (plugins/ themselves never see core_api
               directly — see plugin-api.md).
launcher.py    the composition root — constructs UkoreCore via core_api,
               plus a scoped, deliberately-NOT-re-exported import of
               core.vcs.cloud_sync (see "What's deliberately not
               re-exported" below).
```

An `interface/` (or `plugin_api/`'s own facade) file should never write
`from core.xxx import yyy`. Write `from core_api import yyy` instead. If
something you need isn't re-exported yet, add the re-export to
`core_api/__init__.py`, then add it to this doc.

## Inside `core/` — orientation

`core/` is non-UI logic, no PySide6/Qt imports anywhere in it, organized
into five sub-packages plus a flat handful of app-wide primitives. This
section exists so a session never needs to open `core/` itself just to
find out what's where — everything in it is reachable via `core_api`'s
re-exports above.

- **`storage/`** — `metadata_store.py`'s `MetadataStore` (the Project/Repo
  registry — disk-split into a lightweight index, `data/projects.json`,
  plus one blob per project, `data/projects/<id>.json`), `config_store.py`'s
  `LocalConfigStore` (per-machine) and `SystemConfigStore` (studio-wide,
  cloud-synced), and `atomic_file.py`'s shared `atomic_write`/`utc_now_iso`
  helper. **Never imports `core.vcs.cloud_sync`** — these three stores
  instead take an optional `on_save`/`on_delete` callback (see "What's
  deliberately not re-exported" below). `MetadataStore` also takes
  `on_asset_upload`/`on_asset_missing` — same pattern, but for the binary
  thumbnail/program-icon images under `assets_dir` rather than the JSON
  blob itself: `on_asset_upload(blob_name, local_path)` fires from
  `set_repo_thumbnail`/`set_program_icon` right after the image is copied
  in locally, `on_asset_missing(blob_name, local_path)` fires from
  `resolve_thumbnail_path`/`resolve_program_icon_path` when the local file
  doesn't exist yet — `launcher.py` wires both to lazy `R2JsonSync.push`/
  `.pull` calls (unlike the JSON stores, these images are pulled lazily
  per-file on first read, not eagerly at launch — see
  `developer/app/docs/data-layout.md`).
- **`auth/`** — `token_store.py`'s `SecureTokenStore` (OS-keyring credential
  storage, gitignored-JSON fallback) and `github_auth.py`'s
  `fetch_avatar_bytes`. GitHub login itself (device-code flow) lives
  entirely in the separate `UkoreHubLauncher` repo now, not here.
- **`vcs/`** — `git_service.py`'s `GitService` (git/git-lfs subprocess
  wrapper), `cloud_sync.py`'s `R2JsonSync` (Cloudflare R2 sync — see "What's
  deliberately not re-exported"), `paths.py` (`resolve_repo_path`,
  `sanitize_folder_name` — **see the `ukorehub-core` skill before adding a
  new `resolve_repo_path` call site**, it's creation-time-only),
  `commits_api.py` (GitHub REST commit history) and `repo_access.py`
  (pre-clone access check).
- **`events/`** — `hooks.py`'s `AppLifecycleContext`/`AppLifecycleHooks`
  (the fixed three-point plugin lifecycle) only now. The old
  `bus.py`/`debug_log.py` (`InMemoryEventBus[T]`/`DebugLogBus`/
  `DebugLogEntry`) were retired 2026-08-21 in favor of stdlib `logging` —
  see `interface/qt_log_handler.py`'s `QtLogHandler` (Qt-layer, not
  `core/`-layer, since it subclasses `QObject`) and
  `developer/app/docs/plugins/DebugConsole.md`. `UkoreCore` still holds
  the shared handler instance, now as `core.debug_log_handler`/
  `api.debug_log_handler` (loosely typed `object` in `core_api` to avoid
  `core_api` importing `interface_api`) — but general code should just
  call `logging.getLogger(__name__)` directly instead of going through
  `core`/`api` at all; that property exists only for DebugConsole's own
  page.
- **`extensibility/`** — `loader.py` (plugin discovery/apply — see
  `plugin-api.md` for the plugin-authoring side of this), `config_store.py`'s
  `PluginConfigStore`/`ProjectPluginConfigStore`, `file_opener.py`'s
  `FileOpenerRegistry`/`FileOpenerSpec`.
- **Flat files**: `models.py` (`Project`, `Repo`, `RepoStatus`, `Program`
  dataclasses), `exceptions.py`, `os_utils.py`, `relaunch.py`
  (`relaunch_ukorehub_exe` — spawns `UkoreHub.exe` with PyInstaller onefile
  env vars stripped, see the `ukorehub-interface` skill), `version.py`.

Two persisted-but-effectively-retired `Repo` fields worth knowing about if
you're touching plugin-visibility logic: `Repo.active_plugin_ids` is no
longer read anywhere (kept only so old JSON round-trips) —
`Repo.required_plugin_ids` is the real gate now, for `cache/plugins/`
entries (`interface/repo_settings/requirements_and_plugins_page.py`).

## `UkoreCore` (`core_api/app_core.py`)

The composition facade tying `core/`'s stateful services together into
one object — `launcher.py` constructs exactly one instance per app run and
threads it into `MainWindow`/`PluginAPI` instead of wiring each service
individually.

```python
core = UkoreCore(
    data_dir=data_dir, cache_dir=cache_dir, assets_dir=assets_dir,
    on_metadata_save=..., on_metadata_delete=...,
    on_metadata_asset_upload=..., on_metadata_asset_missing=...,
    on_system_config_save=...,
    debug_log_handler=qt_log_handler,  # optional — None if omitted, no self-construct fallback
)
```

| Attribute | Type | Notes |
|---|---|---|
| `core.metadata` | `MetadataStore` | The Project/Repo registry. |
| `core.system_config` | `SystemConfigStore` | Studio-wide, cloud-synced settings. |
| `core.local_config` | `LocalConfigStore` | Per-machine settings. |
| `core.hooks` | `AppLifecycleHooks` | App-start/repo-changed/app-close subscriber lists — `PluginAPI.on_app_start`/etc. delegate here. |
| `core.git` | `GitService` | Git subprocess wrapper. |
| `core.github_tokens` | `SecureTokenStore` | Cached GitHub token — read only for logout (`clear_github_session`); never used to authenticate anything itself. |
| `core.debug_log_handler` | `object \| None` (really `interface_api.QtLogHandler`) | Shared handler DebugConsole's page reads/subscribes to — `None` if not wired up. |

| Method | Notes |
|---|---|
| `get_active_workspace()` | Returns `(Project \| None, Repo \| None)` the `local_config` currently points at, or `(None, None)` if nothing's active/resolvable. |
| `switch_active_repo(project_id, repo_id)` | Sets the active repo on `local_config`. |
| `clear_github_session()` | Non-Qt half of logout: clears cached token + remembered username/login-at, resets `git`'s token. Does not relaunch `UkoreHub.exe` — that's the caller's job (`interface/main_window.py`'s `_relaunch_to_login`). |

**Deliberately never imports `core.vcs.cloud_sync`** — `on_save`/`on_delete`
callbacks are passed in from `launcher.py` instead (see "What's
deliberately not re-exported" below).

## Re-exported `core/` types

Everything below is importable as `from core_api import X` — never
`from core.xxx import X` in `interface/` or `plugin_api/`'s own facade
files.

**Models** (`core/models.py`): `Repo`, `Project`, `Program`, `RepoStatus`,
`FileChange` (`path`, `change_type` — `"untracked"|"added"|"modified"|
"deleted"|"renamed"`; populates `RepoStatus.unstaged_changes`/
`.staged_changes`, produced by `GitService._parse_status_porcelain`)

**Exceptions** (`core/exceptions.py`): `NotFoundError`, `ConflictError`,
`GitOperationError`, `GitHubAuthError`, `UkoreHubError`, `ValidationError`

**Service types** (for constructor type hints — the actual shared instance
always comes from a `UkoreCore` instance's own attributes, never construct
these yourself): `GitService`, `MetadataStore`, `LocalConfigStore`,
`SystemConfigStore`

**Plugin-loader** (`core/extensibility/loader.py`): `DiscoveredPlugin`,
`PluginManifest`, `PluginLoadFailure`, `discover_plugins`, `apply_plugins`,
`plugin_source`

**Config store classes** (`core/extensibility/config_store.py`):
`PluginConfigStore`, `ProjectPluginConfigStore`

**File opener** (`core/extensibility/file_opener.py`): `FileOpenerRegistry`,
`FileOpenerSpec`

**Events** (`core/events/`): `AppLifecycleContext`, `AppLifecycleHandler`

**Version** (`core/version.py`): `APP_NAME`, `APP_VERSION`

**Misc helpers**: `relaunch_ukorehub_exe` (`core/relaunch.py`),
`migrate_legacy_programs`, `read_project_ids` (`core/storage/metadata_store.py`),
`fetch_avatar_bytes` (`core/auth/github_auth.py`), `check_repo_access`
(`core/vcs/repo_access.py`), `extract_git_repo_name` (`core/vcs/paths.py`),
`open_in_file_explorer`, `open_with_default_app` (`core/os_utils.py`),
`GitHubCommitsApiError`, `download_bytes`, `fetch_commits_for_path`
(`core/vcs/commits_api.py`)

## What's deliberately *not* re-exported

`core.vcs.cloud_sync.R2JsonSync` — `core_api` (and `UkoreCore` itself)
never imports this. Only `launcher.py` and `plugin_api/plugin_api.py` are
allowed their own scoped `from core.vcs.cloud_sync import R2JsonSync`
import. This isolation keeps `boto3` out of `UkoreHubLauncher.exe`'s
frozen build (see `core/vcs/cloud_sync.py`'s own module docstring) — the
cloud-synced stores instead take an optional `on_save`/`on_delete`
constructor callback that `launcher.py` wires up to `R2JsonSync.push`/
`.delete`. `interface/` never needs `R2JsonSync` directly; a plugin needing
read-only access to the built engine uses `api.cloud_sync`
(`plugin_api`'s `PluginAPI.cloud_sync` property), not an import.

## If this doc is missing something

Add the re-export to `app/core_api/__init__.py` first (following the
existing pattern — group by source module, add to `__all__`), then add a
row/entry to this doc in the same commit. Don't have an `interface/` (or
`plugin_api/`) file import `core.*` directly as a workaround — that's
exactly the violation `developer/app/check_import_boundaries.py` checks
for.
