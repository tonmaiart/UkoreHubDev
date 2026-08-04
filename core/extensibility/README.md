# core/extensibility/

The plugin discovery and hook system. No PySide6/Qt imports here —
`hooks.py` deliberately isn't a `QObject` so `core/` stays importable and
testable without a `QApplication`; UI-facing registration (sections,
settings tabs, project-info tabs) is composed on top of these in
`interface/plugin_api.py`, which is the actual `api` object a plugin's
`register(api)` receives.

- `loader.py` — `discover_plugins(roots, api_version)` scans manifest.json +
  entry-point Python files under a list of root directories (`plugins/studio`,
  `plugins/local`) and imports each one; `apply_plugins(discovered, api)`
  calls each one's `register(api)`. Never raises — a broken plugin is
  recorded as a `PluginLoadFailure` and skipped, not a crash. Also has
  `plugin_source()`, deriving `"studio"`/`"local"` from a discovered
  plugin's path.
  `PluginManifest.core: bool` (manifest.json `"core": true`, default
  `false`, added 2026-07-15) flags a plugin as load-bearing for per-repo
  *visibility* — distinct from `PluginLoadFailure` isolation, which still
  applies the same to a core plugin if it fails to import/register.
  `launcher.py` collects `core_plugin_ids` from this flag and passes it to
  `MainWindow`, whose `_apply_plugin_visibility` force-shows a core
  plugin's section regardless of a repo's `active_plugin_ids` allowlist —
  and `interface/settings/enable_plugin_page.py` renders it checked and
  disabled so a manager can't accidentally hide it in the first place. The
  first (and so far only) user is `plugins/studio/project_editor/`: hiding
  it for a repo would remove the only way to switch that repo's active
  repo at all, a real lockout rather than a preference.
- `config_store.py` — `PluginConfigStore`: namespaced, atomic-write JSON
  settings for a single plugin (mirrors `LocalConfigStore`/`SystemConfigStore`
  in `core/store.py`, but with a free-form key/value schema instead of fixed
  fields).
- `hooks.py` — `GitHookEvent`/`GitHookContext`/`HookRegistry`: plain-Python
  pub/sub for git lifecycle events (before/after clone/pull/push/commit),
  fired from `core/git_service.py`.
- `file_opener.py` — `FileOpenerSpec`/`FileOpenerRegistry`: lets a plugin
  claim responsibility for opening certain file extensions (e.g. launching
  Maya with custom env vars instead of the OS default association) when a
  file is opened through Repo Browser (double-click in the file table) —
  never for files opened outside UkoreHub entirely.
- `debug_log.py` — `register_source`/`log`/`entries`/`sources`/
  `add_listener`/`remove_listener`/`clear`: an in-memory, cross-plugin
  debug log bus, added 2026-07-20 alongside `plugins/studio/DebugConsole/`
  (that plugin's own README has the full story — this file is just the
  Qt-free data side of it). Any plugin/core code can call
  `log(source, message)` directly (import the module, no `api` handle
  needed) from anywhere at runtime, not just inside `register(api)` —
  the same "construct/reach directly, convention not import" pattern
  `config_store.py`'s `PluginConfigStore` already relies on elsewhere in
  this codebase. Not persisted (ephemeral, cleared on app restart or via
  DebugConsole's "Clear" button) and capped at 1000 entries.
- `notification_bus.py` — `NotificationEntry`/`push`/`entries`/
  `entries_for`/`add_listener`/`remove_listener`/`clear`: the same
  in-memory, cross-plugin, no-`api`-handle-needed bus pattern as
  `debug_log.py` above, added 2026-08-03 alongside
  `plugins/studio/Notification/` (that plugin's own README has the full
  socket/template contract — this file is just the Qt-free data side of
  it). `push(source, project_id, repo_id, label, ...)` is the "template"
  contract: `repo_id=None` means the notification applies to every repo in
  the project, a specific repo id scopes it to just that repo — the
  producer picks this at push time, there is no user-facing scope toggle.
  Not persisted, same reasoning as `debug_log.py` (a notification's
  `on_click` is a live Python callback that can't survive an app restart
  anyway) and capped at 500 entries.

None of these six files import each other. `hooks.py` and `file_opener.py`
import `core.models` (for `Project`/`Repo`); `config_store.py` imports
`core.store._atomic_write`; `debug_log.py`/`notification_bus.py` have no
internal imports at all. All are absolute imports to modules that live
directly in `core/`, not in this subpackage.

## Plugins

`plugins/studio/` + `plugins/local/` are UkoreHub's own sub-systems —
implemented once, loaded (or not, on failure) once at app startup for
every project alike. A repo *can* additionally hide a loaded plugin's own
sidebar section via `Repo.active_plugin_ids` (Settings > Repo > Enable
Plugin, `interface/settings/enable_plugin_page.py`) — a per-repo
*visibility* toggle, not a per-repo *load* toggle — unless the plugin is
flagged `manifest.json` `"core": true` (`PluginManifest.core`, see
`loader.py` above), which is never hideable this way.
