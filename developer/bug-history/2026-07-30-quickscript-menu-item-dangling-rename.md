# "Quick Script..." menu item crashed with ModuleNotFoundError: QuickScript

## Symptom

Clicking "Quick Script..." in Maya's Ukore Studio Tool menu printed:

```
# Error: ModuleNotFoundError: file <frozen importlib._bootstrap> line 1004: No module named 'QuickScript'
```

## Root cause

Commit `6f842a0` ("Update UkoreShot and UkorePlayblast Plug-ins") deleted
`plugins/studio/MayaToolkit/maya-scripts/QuickScript/` (and a stray
`PythonReader - Copy/` duplicate) — `QuickScript/interface.py` and
`PythonReader/interface.py` had identical header/imports, confirming
`QuickScript` had been renamed to `PythonReader` and the old folder was
being cleaned up as a duplicate. That commit updated the unrelated
`playblast()`/`playblast_options()` functions in the same file
(`UkoreMaya/core/menu_utils.py`) but missed `quick_script()`, which still
called `File.launch("QuickScript")` — a dangling reference to the deleted
toolkit name.
`plugins/studio/MayaToolkit/maya-plug-ins/ukoreMaya.py`'s top-level
"Quick Script..." menu item still wired to it, so the crash only surfaced
when an artist actually clicked that specific item — `python_reader()` /
"Local Script..." (Rig submenu) already called `File.launch("PythonReader")`
correctly and worked fine the whole time, masking the dangling one.

## Fix

`plugins/studio/MayaToolkit/maya-scripts/UkoreMaya/core/menu_utils.py`'s
`quick_script()` now calls `File.launch("PythonReader")`, matching
`python_reader()`. Note this leaves two separate menu items ("Quick
Script..." top-level, "Local Script..." under Rig) launching the same
toolkit — not deduplicated here since that's a menu-layout decision, not
part of the crash fix.

## Lesson

When a toolkit folder under `maya-scripts/` is renamed or deleted as part
of a cleanup (especially "delete a duplicate" cleanups), grep
`maya-plug-ins/` and `UkoreMaya/core/menu_utils.py` for
`File.launch("<OldName>")` before committing — the menu wiring
(`cmds.menuItem(... command=...)`) and the `menu_utils.py` function it
calls are a separate layer from the toolkit folder itself, so deleting/
renaming the folder alone doesn't surface as an import error until someone
actually clicks that specific menu item.
