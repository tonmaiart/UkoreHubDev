# 2026-08-05 — Ukore Reference Editor's Repath button couldn't pick a file, only a folder

## Symptom

Clicking **Repath...** on a row and trying to pick an exact file (rather than
a folder to search) didn't work — the dialog behaved as if only directories
could be selected, and confirming never redirected the row.

## Root cause

`interface.py`'s `_repath_row` called
`cmds.fileDialog2(fileMode=2, caption="Repath...", ...)` with no
`dialogStyle` set, so Maya used its default OS-native dialog on Windows.
Maya's own docs for `fileMode=2` describe it as returning **"the name of a
directory. Both directories and files are displayed in the dialog"** — files
are shown for navigation, but the dialog's native-style implementation on
Windows doesn't let one be picked as the actual return value; the containing
folder comes back either way. `matcher.resolve_manual_target` then treated
that returned path as a folder and ran its recursive filename search instead
of the direct file override the artist actually intended, which fails
whenever the picked folder doesn't happen to contain a same-named file.

## Fix

First pass added `dialogStyle=2` to that `fileDialog2` call, matching the
convention already used everywhere else `fileDialog2` appears in this
codebase (e.g. `MayaToolkit/maya-scripts/tmlib/core/QuickData.py`,
`UkoreMaya/menu/General.py`). Superseded the same day by a cleaner design:
the single ambiguous `fileMode=2` "Repath..." button was split into two
dedicated buttons — **Repath File...** (`fileMode=1`, single existing file,
a direct override) and **Repath Search...** (`fileMode=3`, existing
directory only, same recursive-filename search
`_find_all_missing` already used) — so no call site relies on `fileMode=2`'s
ambiguous "file or folder" contract at all anymore
(`interface.py`'s `_repath_row(row, file_mode, caption)`, `dialogStyle=2`
kept on both).

## Redesign note (same day)

Per user request, replaced the single "Repath..." button with two: "Repath
File..." and "Repath Search...", passing an explicit `file_mode` to a shared
`_repath_row`. This sidesteps the `fileMode=2` ambiguity from the root cause
above entirely rather than just working around it.

## Lesson

`cmds.fileDialog2(fileMode=2, ...)` without an explicit `dialogStyle` is not
a reliable "pick a file OR a folder" dialog on Windows — its native style
only reliably returns a directory, regardless of what looks clickable in the
list. Any new `fileDialog2` call in this codebase should always pass
`dialogStyle=2` explicitly (or `dialogStyle=1` if the native OS look is
specifically wanted and only a single file/existing-file-list mode is used),
rather than relying on Maya's undocumented default — check how the rest of
the codebase already calls `fileDialog2` before adding a new call site.
