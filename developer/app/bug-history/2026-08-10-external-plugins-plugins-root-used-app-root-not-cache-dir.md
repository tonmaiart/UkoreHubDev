# 2026-08-10 — External Plugins page/auto-sync engine pointed at `app/cache/plugins` instead of the real `cache/plugins`

## Symptom

User report: catalog entries added on Settings > Developer > External
Plugins never showed up there, and neither did any already-cloned
`cache/plugins/` folder as an auto-detected "(not catalogued)" row — while
Settings > Repo Setting (Dev) > Requirements & Plugins' External Plugin box
correctly listed real, already-cloned repo plugins. Also relevant to the
2026-08-10 auto-sync engine (see this plugin's README's "Auto-sync
engine"): a required plugin would "clone" successfully (no error) but never
actually become visible anywhere.

## Root cause

`plugins/core/ExternalPlugins/plugin.py` computed the local `cache/plugins/`
root as `api.app_root / "cache" / "plugins"` — i.e. `app/cache/plugins`.
That's wrong: `app/launcher.py`'s own `CACHE_DIR` (module-level, top of the
file) is **not** `REPO_ROOT/cache` at all — it defaults to
`~/Documents/UkoreHub/cache` (`USER_DATA_DIR/cache`), or wherever
`UKOREHUB_CACHE_DIR` points when a real `UkoreHubLauncher.exe` install sets
it — deliberately outside the app folder, per root CLAUDE.md's "Program
folder stays program-only". `launcher.py` itself gets this right:
`cache_plugins_root = cache_dir / "plugins"` (not `REPO_ROOT`-relative),
which is what it hands to both `discover_plugins()` and the built-in
"Plugins" diagnostic tab (`register_builtin_settings_tabs(...,
plugins_root=cache_plugins_root)`). `interface/plugin_api.py` already
exposes the correct value as a public property — `PluginAPI.cache_dir` —
but this plugin's `page_factory` (and the new `_SyncController`, which
copied the same wrong expression) used `api.app_root` instead, which is
just `REPO_ROOT` (`interface/plugin_api.py`'s `app_root` property,
`launcher.py`'s `app_root=REPO_ROOT`).

Net effect: this plugin scanned/cloned into `app/cache/plugins`, a folder
that (outside a dev checkout with `UKOREHUB_CACHE_DIR` unset and
`app/cache/plugins` never otherwise created) simply doesn't exist and isn't
where any real clone lives — while every *other* consumer of "where are
cache/plugins/ clones" (`launcher.py`'s `discover_plugins()` call,
`requirements_and_plugins_page.py`, which is threaded `plugins_root` from
`launcher.py` directly) used the correct `cache_dir / "plugins"`. This
predates the 2026-08-10 auto-sync engine — `plugin.py`'s `page_factory` had
this wrong expression already; the new `_SyncController.__init__` just
copied the same pattern into a second call site.

## Fix

Both call sites in `plugins/core/ExternalPlugins/plugin.py` now use
`api.cache_dir / "plugins"` instead of `api.app_root / "cache" / "plugins"`
— `api.cache_dir` is `PluginAPI`'s existing public property for exactly
this value, already used correctly elsewhere in the app.

## Lesson

`api.app_root` (`REPO_ROOT`, the `app/` folder itself) and `api.cache_dir`
(`CACHE_DIR`, deliberately *not* under `app/` in a real install — see root
CLAUDE.md's "Program folder stays program-only") are two different things
that happen to coincide only in a narrow dev-checkout case where
`UKOREHUB_CACHE_DIR` is unset and nothing has ever created
`app/cache/plugins`. Manually reconstructing `cache/plugins/`'s path as
`api.app_root / "cache" / "plugins"` instead of using `api.cache_dir /
"plugins"` will silently point at a folder nothing else in the app uses —
no error, just an empty list and clones nobody else can see. Any new code
that needs "the local cache/plugins/ root" should use `api.cache_dir /
"plugins"` (matching `launcher.py`'s own `cache_plugins_root`), never
derive it from `api.app_root`.
