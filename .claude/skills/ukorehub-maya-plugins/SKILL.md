---
name: ukorehub-maya-plugins
description: Recurring gotchas specific to UkoreHub's Maya-integrated plugins (C:\Tonmai\UkoreHub) — the maya-scripts/ and maya-plug-ins/ family (MayaToolkit, PublishApi, UkoreReferenceEditor, maya_launcher, RigPublisher, ModelPublisher, AnimationPublisher, MayaNgskin, UkoreBrowser, AdvancedSkeleton, mGear, DreamwallPicker, StudioLibrary). Use this whenever reading, writing, or debugging any file under a plugin's maya-scripts/ or maya-plug-ins/ subfolder, or any Maya-API call (cmds.fileDialog2, cmds.file, initializePlugin, evalDeferred) — even if the user doesn't say "Maya" explicitly (e.g. "the repath button only lets me pick a folder", "the menu item crashes with ModuleNotFoundError", "the reference doesn't auto-redirect on first open").
---

# UkoreHub Maya plugins — authoring pitfalls

These are Maya-API/mayapy-environment gotchas that recurred across more than
one plugin in this family — see the `ukorehub-plugin` skill first for the
general "stay inside one plugin's folder" discipline; this skill is the
Maya-specific technical traps on top of that.

## Menu wiring is a separate layer from the toolkit folder

Renaming or deleting a `maya-scripts/<Name>/` subfolder doesn't
automatically update the menu items that launch it — `menu_utils.py`-style
menu registration and `maya-plug-ins/*.py`'s `File.launch("<Name>")` calls
reference the old name by string, with no import-time check. After
renaming/removing a `maya-scripts/` subfolder, grep `maya-plug-ins/` and any
`menu_utils.py` for the old name before committing — a dangling reference
doesn't surface until an artist clicks that specific menu item
(`ModuleNotFoundError` at click time, not load time).

## `-prompt false` suppresses Maya's native file dialog, `-loadReferenceDepth` does not

`-loadReferenceDepth "none"` on a `file` command only controls whether a
reference's *content* loads — it does not stop Maya's own path-existence
validation, which is what triggers the native "could not find file" dialog.
To suppress that interactive dialog, pass `-prompt false` (Maya's actual
dialog-suppression flag) instead. Don't assume a flag whose name matches the
symptom also controls the dialog — verify empirically (e.g. a Script Editor
print) before trusting the fix.

## Scene-message callbacks needed for the *first* file-open must register synchronously

A plugin callback that must already be in place before Maya's very first
scripted file-open cannot be registered via `cmds.evalDeferred` inside
`initializePlugin` if that same `-open` call can happen synchronously later
in the same `-command` MEL string that force-loaded the plugin —
`evalDeferred` never gets a turn until the whole string finishes running.
Only defer setup pieces that genuinely need the UI to exist yet (menus);
register scene-message callbacks (`om.MSceneMessage.addCallback` etc.)
synchronously, directly in `initializePlugin` itself.

## Guard an optional third-party import on a shared eager-load path

A third-party dependency needed by only one optional feature must never sit
at module top level in a file reachable from a shared eager-load path (e.g.
`Plugin.reload_scripts()` importing every module under `tmlib.core`) — one
artist missing that dependency (e.g. ngSkinTools2) breaks the whole plugin
for them, not just the one feature. Guard it with `try/except ImportError`
plus an `_AVAILABLE` flag, and double-check the import statement itself
lives inside the `try` block meant to catch its absence — deferring the
import inside a function is not enough if the function is still called
unconditionally elsewhere.

## `maya-scripts/**/repo_paths.py` construct core stores directly off disk

Under `mayapy`, these Maya-side scripts have no `PluginAPI` handle — they
construct `LocalConfigStore`/`MetadataStore`-equivalents directly against a
hardcoded on-disk path. If a store's real file location ever moves (e.g.
`data/` → `cache/`, or any future reorg), grepping only `core/`/`interface/`
for the old path is not enough: grep for the store-class-construction call
itself (`LocalConfigStore(`, `MetadataStore(`) across the whole repo,
including every `maya-scripts/**/repo_paths.py`. A stale path here produces
no exception — the store just silently loads empty defaults forever.

## Always pass `dialogStyle` explicitly to `cmds.fileDialog2`

`cmds.fileDialog2(fileMode=2, ...)` without an explicit `dialogStyle` is not
a reliable "pick a file OR a folder" dialog on Windows — its native style
only reliably returns a directory. Always pass `dialogStyle=2` for any new
"file or folder" picker (or `dialogStyle=1` for a single-file-only native
look). When the ambiguity itself is the actual problem (not just a missing
flag), prefer splitting into two dedicated buttons — one `fileMode=1`, one
`fileMode=3` — over trying to make one button cover both cases.
