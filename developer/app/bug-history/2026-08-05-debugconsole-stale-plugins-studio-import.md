# 2026-08-05 — DebugConsole plugin silently failing to load (stale `plugins.studio` import)

## Symptom

The Debug Console sidebar section never appeared, with no error shown
anywhere in the UI — discovered while auditing every plugin's `manifest.json`
for cross-plugin `requires`, not from a user report.

## Root cause

`plugins/core/DebugConsole/plugin.py` imported
`from plugins.studio.DebugConsole.debug_console_page import DebugConsolePage`
— `plugins/studio/` hasn't existed since an earlier rename to
`plugins/core/`/`plugins/repo_internal/` (other files still carry stale
`plugins/studio/...`/`plugins/repo_internal/`-mix references in comments and
READMEs, but this one was a real, executed import statement, not just
prose). `core/extensibility/loader.py`'s `_load_one` wraps the entry-point
import in a bare `except Exception`, recording a `PluginLoadFailure` and
skipping the plugin instead of raising — by design, so one broken plugin
can't take down the app — but that also means this `ModuleNotFoundError`
had no visible surface anywhere in the running app.

## Fix

Changed the import to
`from plugins.core.DebugConsole.debug_console_page import DebugConsolePage`,
matching where `manifest.json`/`plugin.py` actually live.

## Lesson

`discover_plugins`'s never-raises design (see `core/extensibility/README.md`)
means a plugin can be completely dead — zero errors, zero log lines a normal
user would ever see — for an arbitrary length of time after a folder rename,
since nothing surfaces `PluginLoadFailure`s outside of explicitly checking
for them. After renaming a `plugins/<root>/` directory (or moving a plugin
between `core`/`repo_internal`/`studio`-style roots), grep every plugin's own
`plugin.py` for `from plugins.<old_root>` / `import plugins.<old_root>`
literally, not just its README — READMEs can carry stale path references
indefinitely without anything breaking, but a stale import in the entry
point itself silently kills the whole plugin.
