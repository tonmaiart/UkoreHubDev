# 2026-08-05 — Ukore Reference Editor's auto-redirect/auto-load never ran for the very first Launch-triggered scene open

## Symptom

Launching a Maya file through UkoreHub (Maya Launcher) left every reference
unloaded, even the ones whose file resolved fine (status "ok"/"outdated") —
they stayed unloaded until the artist manually clicked Rescan, "Load All
References", or reopened the same scene by hand via Maya's own File > Open.
A later manual File > Open in the same Maya session worked correctly.

## Root cause

`plugins/repo_internal/maya_launcher/plugin.py`'s `_set_project_and_open_command`
forces every reference to come in unloaded
(`-loadReferenceDepth "none" -prompt false`) specifically so
`UkoreReferenceEditor.core.auto_check_and_redirect` — registered as a
`kAfterOpen` callback in
`plugins/repo_internal/MayaToolkit/maya-plug-ins/ukoreMaya.py` — can redirect
anything broken and then explicitly (re)load every reference that already
resolves (`core.py`'s `auto_check_and_redirect`, the `loaded_as_is` loop).
That callback registration itself
(`_register_ukore_reference_editor_callback()`) lived inside
`_post_load_setup`, which `initializePlugin` only runs via
`cmds.evalDeferred` — deliberately, so `loadMenu()`'s
`cmds.menu(parent="MayaWindow")` doesn't fire before "MayaWindow" exists at
Maya startup. But `maya_launcher`'s `open_maya_file` force-loads this plugin
and issues `file -open` in the *same* `-command` MEL string
(`_force_load_plugins_command(...) + _set_project_and_open_command(...)`) —
`kAfterOpen` fires synchronously as part of that `file -open` call, which
completes before Maya's evalDeferred queue ever gets a turn. So for the very
first scene opened this way, the kAfterOpen callback simply wasn't
registered yet when it fired — `auto_check_and_redirect` never ran for it at
all, leaving every reference (broken or not) sitting unloaded. Only a
*later* File > Open in the same session (by which point the deferred setup
had long since run) actually triggered it.

## Fix

Split `_post_load_setup` in
`plugins/repo_internal/MayaToolkit/maya-plug-ins/ukoreMaya.py`:
`_register_ukore_reference_editor_callback()` now runs immediately, directly
inside `initializePlugin`, since `om.MSceneMessage.addCallback` has no
"MayaWindow" UI dependency the way `loadMenu()` does — only `loadMenu()` and
`function.auto_launch_ukore_file_browser()` stay behind the
`cmds.evalDeferred` call.

## Lesson

A plugin callback that must be in place before Maya's *very first* scripted
`file -open` (as opposed to a later interactive one) cannot be registered
via `cmds.evalDeferred` inside `initializePlugin` if that same `-open` call
can happen synchronously later in the exact same `-command` MEL string that
force-loaded the plugin — evalDeferred never gets a turn until the whole
`-command` string finishes running, by which point the event it needed to
catch has already fired. Only defer the pieces of plugin setup that actually
require the UI to exist (menus, docked windows); register scene-message
callbacks (`om.MSceneMessage.addCallback`, `om.MDGMessage`, etc.)
synchronously in `initializePlugin` itself. When adding a new `kAfterOpen`/
`kBeforeOpen`/etc. callback to a Maya plug-in that Maya Launcher force-loads
via its `-command` string, check whether Maya Launcher's own `file -open`
can run before the callback is registered — same question as this bug, for
the next tool that needs one.
