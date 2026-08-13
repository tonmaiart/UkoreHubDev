# plugins-guide.md — how to author an `app/plugins/core/<Name>/` plugin

Moved here (2026-08-13) from `app/plugins/README.md`, which was removed —
see root `CLAUDE.md`'s "Reading this codebase" section for why. This is
the "how do I write one" guide; see
[`core-api.md`](core-api.md)'s "Inside `core/`" section (`extensibility/`
entry) for the "how does discovery/loading work" reference, and
[`plugin-api.md`](plugin-api.md) for the full `PluginAPI` command
reference. For a specific existing plugin's own implementation details,
see [`plugins/`](plugins/).

Two roots, both scanned by the same `discover_plugins()` (see
`launcher.py`) — they differ along two independent axes: whether the
plugin ships bundled with the app vs. is fetched separately, and whether
it's on by default per repo vs. opt-in:
- `plugins/core/` — git-tracked, ships bundled with the app (distributed
  via `self_update.py`'s whole-tree `git pull`), **always on** for every
  repo — no per-repo opt-out at all. Explorer, Submit, and Software Linker
  all live here — reserve this root for functionality every repo
  genuinely needs; anything repo-specific belongs in `cache/plugins/`
  instead.
- `cache/plugins/` (outside `plugins/`, at the app root, gitignored) —
  **repo plugins**: each one is its own separate git clone (its own
  remote/history, not part of this repo at all), fetched/updated on demand
  only for a repo that requires it. Not bundled with the app in any sense —
  see `plugin_source()` returning `"repo"` for one of these. A `plugin.py`
  here locates its own folder via `Path(__file__).resolve().parent` rather
  than `api.app_root`, since it isn't at a fixed path relative to the app
  install. There's no auto-fetch/clone mechanism implemented anywhere yet
  — `launcher.py` only `mkdir`s `cache/plugins/` and discovers whatever's
  already physically cloned there.

There is no more `plugins/local/` or `plugins/repo_internal/` — both
removed once unused/migrated out to standalone repo-plugin clones.
Prototype a new plugin directly under `plugins/core/` (if genuinely
universal) or as its own `cache/plugins/` clone (if repo-specific).

## Working on a single plugin — stay inside its folder

When a task names a specific plugin (or the target path is under
`plugins/core/<Name>/` or `cache/plugins/<Name>/`), read and edit **only
that folder**. Don't open a sibling plugin "just in case" — each one is
independent, and reading one has zero information value for working on a
different one. Check that plugin's own doc under
[`developer/app/docs/plugins/`](plugins/) first if it has one.

If a task genuinely needs data from another plugin, that's almost always
the shared-`plugin_config_store` convention below (a `plugin_id` string +
a documented JSON shape), not a reason to read the other plugin's source.
The one real exception is explicit cross-plugin debugging — say so and
read both deliberately, rather than defaulting to broad exploration for a
single-plugin task. See the `ukorehub-plugin` skill for the fuller writeup.

## Minimum folder shape

```
plugins/core/YourPluginName/
  manifest.json
  plugin.py
```

`manifest.json`:
```json
{
  "id": "your_plugin",
  "name": "Your Plugin",
  "version": "0.1.0",
  "api_version": 1,
  "entry_point": "plugin.py",
  "description": "One sentence describing what this plugin registers.",
  "requires": ["other_plugin_id"]
}
```
`id` must be globally unique across every plugin. `api_version` must match
the app's current `PLUGIN_API_VERSION` (`plugin_api/plugin_api.py`) or
your plugin is skipped with a `PluginLoadFailure`, not a crash.

`requires` (optional, defaults to `[]`) lists the plugin `id`s this plugin
can't function without — for a `cache/plugins` plugin that depends on
another opt-in plugin also being enabled for the repo, not for declaring a
load-order dependency (there is none — see above). It's only enforced at
the UI layer, in Settings > Requirements & Plugins
(`interface/repo_settings/requirements_and_plugins_page.py`): enabling a
plugin with unmet requirements prompts to enable those too; disabling a
plugin something else still requires prompts a "this will break X"
warning. `discover_plugins`/`apply_plugins` themselves never read or
enforce it — a plugin missing its requirement still loads and registers
fine, it just won't have been offered as enabled together automatically
outside that one settings page.

`entry_point` (conventionally `plugin.py`) needs exactly one function:
```python
def register(api) -> None:
    ...
```
Called once at app startup (`core/extensibility/loader.py`'s
`apply_plugins`), after every plugin has been discovered but with **no
guaranteed order** between plugins — don't write a `register(api)` that
assumes another specific plugin has already run. A broken `register(api)`
(raises, or the module has no `register` at all) is caught and recorded as
a `PluginLoadFailure`, not a crash.

## Multi-file plugins: real sibling imports, not `importlib` tricks

A single-file plugin (`software_linker`) imports its types from
`plugin_api` (never `core.*`/`interface.*` directly — see "`api`" below,
and `plugin-api.md` for the shared-UI widgets `plugin_api` re-exports from
`interface_api`) — nothing to coordinate. A **multi-file** plugin
(`explorer`, `submit` — each 6-8 files) needs its own files to import each
other too. The loader only ever imports the `entry_point` file directly
(via `importlib.util.spec_from_file_location`, a standalone load) — but
that entry file's own `import` statements are resolved normally, so a
multi-file plugin folder is set up as a **real, plain Python package**: an
empty `__init__.py` in the plugin's own folder (plus one in `plugins/` and
`plugins/core/` themselves, already present), so sibling files import each
other with ordinary absolute imports — `from
plugins.core.explorer.browser_widget import RepoBrowserWidget`, not a
relative import (the entry file's own `__name__` isn't
`plugins.core.explorer.plugin`, so `from .browser_widget import ...` would
not work — see `plugins/core/explorer/plugin.py` for the working
pattern). Note this convention doesn't extend to `cache/plugins/` — a repo
plugin isn't guaranteed to live under `plugins/` at all (that's the whole
point), so its own sibling files should import via
`Path(__file__).resolve().parent` relative lookups instead, not a
`plugins.*` dotted path (see `cache/plugins/mGear/plugin.py`'s
`tool_root` for the pattern). This is scoped to *your own plugin's*
files — reaching into another plugin's package this way is still not a
thing to do; see "Sharing data with another plugin" below instead.

## `api` — what `register(api)` receives

`api` is a `PluginAPI` instance (`plugin_api/plugin_api.py`) — see
[`plugin-api.md`](plugin-api.md) for the full property/method reference.
**A plugin file should never write `from core.xxx import yyy` directly**
— `core/` is closed to everything outside itself and `plugin_api/`; write
`from plugin_api import yyy` instead.

## Sharing data with another plugin: `plugin_config_store`, not imports

`api.plugin_config_store(plugin_id, shared=True|False)` returns a
`PluginConfigStore` — free-form JSON, namespaced by `plugin_id`. Two
unrelated plugins that independently construct a store with the **same
`plugin_id` string** share the same file — no coupling, no import, just
agreeing on a string and a JSON shape in advance. `shared=True` writes to
the git-tracked studio config dir; `shared=False` writes to the gitignored
per-machine dir. `maya_launcher`'s `plugin.py` (its own `cache/plugins/`
clone) reading `plugins/core/software_linker`'s per-machine `maya.exe`
path via `api.plugin_config_store("software_linker", shared=False)` is the
real worked example, without importing SoftwareLinker's code at all.

**Project/repo-scoped data belongs on the Repo itself, not here.** If what
you're storing is always keyed by exactly one `(project_id, repo_id)` pair
(a per-repo setting, a per-repo connection list, ...), use
`api.metadata.get_repo_plugin_data(project_id, repo_id, plugin_id)`/
`set_repo_plugin_data(...)` instead — it lives in `Repo.plugin_data`
(`core/models.py`), inside that repo's own project blob
(`data/projects/<project_id>.json`, see `app/data/README.md`), so a
repo-level edit only ever pushes/conflicts that one project, not a
separate studio-wide file every repo in every project shares.

**Data scoped to the whole active Project (not a specific repo) but that
shouldn't be studio-wide either** — e.g. it's inherently per-session, like
`maya_launcher`'s `MAYA_ENV_BRIDGE_PLUGIN_ID` contributions (several
plugins each write their own env-var contribution during `register(api)`,
`maya_launcher` merges them at Maya-launch time; none of it needs to
outlive the running project) — use
`api.project_plugin_config_store(plugin_id)` instead. Same `.get`/`.set`
contract as `PluginConfigStore`, but backed by `Project.plugin_data`
(`core/models.py`) via `core/extensibility/config_store.py`'s
`ProjectPluginConfigStore`, riding on that project's own
already-cloud-synced blob — no separate `data/plugins/core/<id>.json`
file. Returns `None` when no project is active yet; callers should skip
their own write/read rather than assume a store always exists.

Reserve `plugin_config_store(shared=True)` for data that's genuinely
studio-wide or spans projects (a global catalog, ...) —
`plugins/core/project_editor/pipeline_store.py` is the worked example.

## `SectionSpec.wire`/`UICommandService`: cross-plugin UI coordination, not imports

If one plugin's page needs to trigger a specific behavior in another
plugin's page (e.g. Submit's "Inspect in Explorer" jumping to Explorer and
focusing a file), don't import the other plugin's page type. Use:
- A plain string `SectionRegistry` key (e.g. `"repo_browser"`) — stable,
  documented in the target plugin's own doc under
  [`developer/app/docs/plugins/`](plugins/), and doesn't fail your
  `register(api)` if the other plugin is ever missing/broken.
- An optional protocol method on the target page (e.g.
  `browse_to_path(path)`, mirroring the existing `set_repo()` convention
  every page already implements) — `UICommandService.navigate_and_focus(key,
  path)` (`plugin_api/registries/section_registry.py`) calls it
  generically via `getattr`/`callable`, without `interface/main_window.py`
  or your plugin needing to import the target page's type. See
  `plugins/core/submit/plugin.py`'s `_wire` for the working example.

## Testing

`plugin.py` files aren't reachable by normal `import` in a pytest test
*from outside their own package* (the loader always imports the
`entry_point` standalone via `importlib.util.spec_from_file_location`,
regardless of whether the folder is also a real package internally). If
`register(api)` or a helper is worth covering:
- Pure, Qt-free logic → extract it into a real `core/` module and test it
  normally.
- Logic that only makes sense inside the plugin → verify with a throwaway
  scratchpad script that loads the module the same way the real loader
  does.
