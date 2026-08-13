# plugins/core/DebugConsole/

Moved here (2026-08-13) from `app/plugins/core/DebugConsole/README.md`
(fixing a couple of stale pre-2026-08-04 path references along the way —
`plugins/studio/` → `plugins/core/`, `core/extensibility/debug_log.py` →
`core/events/debug_log.py`). See `plugins-guide.md` for the general
plugin-authoring conventions this plugin follows.

A live viewer for `core/events/debug_log.py`'s in-memory debug log bus —
any plugin can call `api.debug_bus.log(source, message)` from anywhere at
runtime and see it show up here immediately, without needing a console
window (this app is normally launched via `pythonw.exe`, no console at
all — see the `ukoreshot` skill's native-widget debugging note for why that
mattered). Added 2026-07-20 to debug a
UkoreShot "brush doesn't paint" investigation; kept as a general-purpose
tool since the underlying bus is generic, not plugin-specific.

Living under `plugins/core/` makes this section always visible for every
repo, no per-repo opt-out at all — a debug console is orthogonal to which
repo is active, so gating it per-repo like an artist-facing tool would
just mean re-enabling it for every existing and future repo for no
benefit.

## Files

- `manifest.json` — plugin id `debug_console`.
- `plugin.py` — `register(api)`: builds one `DebugConsolePage` and
  registers it as a section (order 900, near the bottom of the sidebar —
  this is a developer tool, not meant to be prominent), with
  `QStyle.SP_MessageBoxInformation` as its sidebar icon (built-in Qt icon,
  not a bundled bitmap — see `interface.md`'s Zero QSS Policy section).
- `debug_console_page.py` — `DebugConsolePage`: a source filter
  (`QComboBox`, "All sources" + every name `debug_bus.sources()` knows
  about, rebuilt whenever a new source appears) above a read-only,
  monospace `QPlainTextEdit` log view, plus a "Clear" button
  (`debug_bus.clear()`). Subscribes once via `debug_bus.add_listener` in
  `__init__` and never unsubscribes — this page is built once in
  `plugin.py`'s `register(api)` and lives for the app's whole lifetime,
  same as every other plugin's `page_factory`-returned instance, so
  there's no natural teardown point to unsubscribe at.

## Using this from another plugin

```python
api.debug_bus.register_source("YourPlugin.SomeFeature")  # optional — log() auto-registers too

api.debug_bus.log("YourPlugin.SomeFeature", "something happened")
```

`api.debug_bus` (`PluginAPI`, `plugin_api/plugin_api.py`) is the same
`DebugLogBus` instance (`core/events/debug_log.py`, owned by
`core_api/app_core.py`'s `UkoreCore`) DebugConsole's own page subscribes
to — there is exactly one shared instance for the whole app run, same
"agree on a convention, don't import" pattern used elsewhere in this
codebase (see `plugins-guide.md`'s "Sharing data with another plugin"),
just for log messages instead of persisted JSON. Safe to call from deep
runtime code (a widget's `mousePressEvent`, a Maya-side script, etc.), not
just inside `register(api)`. Not persisted — cleared on app restart or via
the "Clear" button — and capped at 1000 entries; this is a live
troubleshooting aid, not an audit log.

**Working here:** this plugin has zero producer-specific code — it only
reads the generic `debug_bus`. Producers include the `"CloudSync"` source
logged by `launcher.py`'s startup pull/`_push_shared_blob` and
`plugin_api/plugin_api.py`'s `plugin_config_store(shared=True)`
pull/push — every cloud pull, push, conflict, and failure around
`core/vcs/cloud_sync.py` shows up here. Reaching into a specific
producer's code from here would violate the same "convention not import"
boundary this plugin exists to demonstrate — don't.
