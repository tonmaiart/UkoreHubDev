# 2026-08-04 — Logout crashed UkoreHub.exe with "Failed to load Python DLL"

## Symptom

Every time a user clicked Logout (Settings > Common), the app closed as
expected, but the relaunched `UkoreHub.exe` immediately showed a native
Windows error dialog instead of the login screen:

```
Failed to load Python DLL
'C:\Users\<user>\AppData\Local\Temp\_MEI######\python314.dll'.
LoadLibrary: The specified module could not be found.
```

100% reproducible on every logout, on every machine — not intermittent.

## Root cause

`interface/main_window.py`'s `_relaunch_to_login()` (added when GitHub
login moved out of the app into the launcher exe — see
`developer/packaging/updater.py`) spawns a fresh `UkoreHub.exe` via
`subprocess.Popen([str(exe_path)], cwd=str(_REPO_ROOT))` with no `env=`
override, so it inherits the **full** environment of the process running
it.

That process (`pythonw launcher.py`) was itself spawned by
`developer/packaging/updater.py`'s `_launch()` — also with no `env=`
override — from *inside* the very first `UkoreHub.exe` bootloader process.
PyInstaller's onefile bootloader sets `_PYI_APPLICATION_HOME_DIR`,
`_PYI_ARCHIVE_FILE`, and `_PYI_PARENT_PROCESS_LEVEL` in its own process
environment (support for `multiprocessing` inside a frozen onefile app,
so a child process reuses the parent's already-extracted payload instead
of re-extracting). Since neither hand-off strips these, they survive the
whole chain: original `UkoreHub.exe` → `pythonw launcher.py` → the new
`UkoreHub.exe` spawned by logout.

A onefile bootloader that sees `_PYI_APPLICATION_HOME_DIR` already set
skips its own self-extraction and tries to load `python314.dll` straight
from that inherited path — but that path was the *original* process's
`_MEI######` temp folder, which its bootloader already deleted on exit by
the time logout happens. Confirmed by capturing the real environment right
before `_launch()`'s `subprocess.Popen` call, then reproducing the exact
error on demand by setting those three variables (pointing at an
already-deleted folder) before launching `UkoreHub.exe` from a plain
shell — 100% reproducible either way.

## Fix

`_relaunch_to_login()` now builds a stripped environment (drops every key
starting with `_PYI_`) and passes it explicitly via `env=` to
`subprocess.Popen`, forcing the new `UkoreHub.exe` to do a genuine fresh
self-extraction instead of trying to reuse a stale, already-deleted one.

## Lesson

Any `subprocess.Popen(...)` that spawns **another PyInstaller onefile exe**
from a process descended from an already-running onefile exe must not
blindly inherit the environment — PyInstaller's bootloader leaves
`_PYI_*` breadcrumbs in `os.environ` for its own `multiprocessing` support,
and they poison a *second, unrelated* onefile launch further down an
inheritance chain, not just literal `multiprocessing.Process` children.
This only bites when one onefile exe (re)launches another onefile exe as a
subprocess — spawning a plain, non-frozen interpreter (like
`updater.py`'s own `_launch()` spawning `pythonw launcher.py`) is
unaffected, since a normal Python process never reads `_PYI_*` at all.
If a future change adds another place that spawns `UkoreHub.exe` (or any
other onefile-built exe in this repo) from within the running app, strip
`_PYI_`-prefixed env vars there too.
