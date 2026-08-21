# plugins/core/DebugConsole/

Moved here (2026-08-13) from `app/plugins/core/DebugConsole/README.md`
(fixing a couple of stale pre-2026-08-04 path references along the way —
`plugins/studio/` → `plugins/core/`, `core/extensibility/debug_log.py` →
`core/events/debug_log.py`). See `plugins-guide.md` for the general
plugin-authoring conventions this plugin follows.

A live viewer for every `logging.getLogger(...)` record the app emits —
any module anywhere (core/, interface/, a plugin) just calls
`logging.getLogger("SomeName").info(...)` with the stdlib `logging`
module, no `api`/bus threading needed at all, and it shows up here
immediately, without needing a console window (this app is normally
launched via `pythonw.exe`, no console at all — see the `ukoreshot`
skill's native-widget debugging note for why that mattered). Added
2026-07-20 to debug a UkoreShot "brush doesn't paint" investigation;
migrated from a bespoke `DebugLogBus`/`InMemoryEventBus` pub/sub bus to
stdlib `logging` + `interface/qt_log_handler.py`'s `QtLogHandler` on
2026-08-21, so producers get standard log levels/formatting for free and
no longer need any reference threaded through to log.

Living under `plugins/core/` makes this section always visible for every
repo, no per-repo opt-out at all — a debug console is orthogonal to which
repo is active, so gating it per-repo like an artist-facing tool would
just mean re-enabling it for every existing and future repo for no
benefit.

## Files

- `manifest.json` — plugin id `debug_console`.
- `plugin.py` — `register(api)`: if `api.debug_log_handler is None`
  (no QApplication/launcher.py logging wiring, e.g. a bare test
  construction of `UkoreCore`), skips registering entirely. Otherwise
  builds one `DebugConsolePage` and registers it as a section (order 900,
  near the bottom of the sidebar — this is a developer tool, not meant to
  be prominent), with `QStyle.SP_MessageBoxInformation` as its sidebar
  icon (built-in Qt icon, not a bundled bitmap — see `interface.md`'s Zero
  QSS Policy section).
- `debug_console_page.py` — `DebugConsolePage`: a source filter
  (`QComboBox`, "All sources" + every distinct `logging.LogRecord.name`
  `handler.sources` has seen, rebuilt whenever a new one appears) above a
  read-only, monospace `QPlainTextEdit` log view (each line formatted via
  `handler.format(record)`, using `interface/qt_log_handler.py`'s
  `"[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s"` format), plus a
  "Clear" button (`handler.clear()`). Subscribes once via
  `handler.log_record_emitted.connect(...)` in `__init__` and never
  unsubscribes — this page is built once in `plugin.py`'s `register(api)`
  and lives for the app's whole lifetime, same as every other plugin's
  `page_factory`-returned instance, so there's no natural teardown point
  to unsubscribe at.

## Using this from another plugin

No `api` involvement at all — just the stdlib `logging` module, from
anywhere (a widget's `mousePressEvent`, a Maya-side script, etc.), not
just inside `register(api)`:

```python
import logging

logger = logging.getLogger("YourPlugin.SomeFeature")
logger.info("something happened")
logger.warning("something worth flagging happened")
```

No registration call needed — DebugConsole's source filter picks up a new
`logger.name` automatically the first time it logs anything, same
"auto-registers" behavior the old bus had, just automatic every time now.

Under the hood, every `logging.getLogger(...)` call in the whole app
(`core/`, `interface/`, any plugin) funnels into the root logger, which
`launcher.py` attaches `interface_api.QtLogHandler` (defined in
`interface/qt_log_handler.py`) to right after constructing `QApplication`
— `core_api/app_core.py`'s `UkoreCore` holds that one shared instance as
`core.debug_log_handler`/`api.debug_log_handler`, and DebugConsole's own
page is the only thing that actually reads it (see that property's own
docstring: general plugin code should never need `api.debug_log_handler`
— just call `logging.getLogger(__name__)` directly). Not persisted —
cleared on app restart or via the "Clear" button — and capped at 1000
entries (the handler's `max_entries` constructor param); this is a live
troubleshooting aid, not an audit log. `QtLogHandler` also mutes
`boto3`/`botocore`/`urllib3`/`s3transfer` to `WARNING` so
`core/vcs/cloud_sync.py`'s R2 client doesn't flood this view.

**Working here:** this plugin has zero producer-specific code — it only
reads the generic `QtLogHandler`. Producers include the `"CloudSync"`
logger used by `launcher.py`'s startup pull/`_push_shared_blob` and
`plugin_api/plugin_api.py`'s `plugin_config_store(shared=True)`
pull/push — every cloud pull, push, conflict, and failure around
`core/vcs/cloud_sync.py` shows up here. Reaching into a specific
producer's code from here would violate the same "convention not import"
boundary this plugin exists to demonstrate — don't.
