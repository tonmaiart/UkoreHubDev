# Maya's native "could not find file" dialog still appeared despite `-loadReferenceDepth "none"`

## Symptom

Opening a Maya scene with a broken reference through UkoreHub's Maya
Launcher still showed Maya's own native "could not find file" dialog, even
after `plugins/core/maya_launcher/plugin.py`'s `open_maya_file` was
updated to add `-loadReferenceDepth "none"` to the `file -open` call
whenever `plugins/core/UkoreReferenceEditor` (named `ReferenceRedirector`
at the time this bug was found, renamed the same day) is enabled for the
launching repo (see that plugin's README's "Beating Maya's own native 'could not find
file' dialog" section). Confirmed via a Script Editor diagnostic print
(`_set_project_and_open_command`'s `diagnostic` MEL line) that the flag was
in fact being applied — the dialog still appeared anyway.

## Root cause

`-loadReferenceDepth "none"` only controls whether Maya loads a reference's
*content* once its reference node is created during `file -open` — it does
**not** stop Maya from performing its own path-existence validation for
every reference node regardless of the load-depth setting. It's that
validation step, not the content-load step, that triggers the native
"could not find file" dialog. Deferring the load therefore had no effect on
suppressing it; both steps happen, just independently of each other.

## Fix

`plugins/core/maya_launcher/plugin.py`'s `_set_project_and_open_command`
now also adds `-prompt false` to the same `file -open` call whenever
`defer_reference_load` is set (alongside `-loadReferenceDepth "none"`) —
Maya's own documented flag for suppressing interactive `file`-command
dialogs, which does cover reference-path-not-found prompts. Confirmed
working against a real broken reference on 2026-08-03.

## Lesson

A Maya `file` command flag that sounds like it should suppress a given
interactive behavior isn't necessarily the flag that actually controls
whether Maya shows a *dialog* about that behavior — path validation and
content loading are separate steps in Maya's reference resolution, each
gated by its own flag (`-loadReferenceDepth` for loading,
`-prompt` for interactivity). When trying to suppress a native Maya dialog
during a scripted `file -open`, reach for `-prompt false` (Maya's actual
"no interactive dialogs" switch) rather than assuming a flag whose name
matches the *symptom* (e.g. "reference depth" for a reference-related
dialog) also controls whether it's shown — and verify empirically (e.g. via
a Script Editor print, same as this plugin's own diagnostic) rather than
trusting documentation-only reasoning, since neither flag's docs spell out
this distinction clearly.
