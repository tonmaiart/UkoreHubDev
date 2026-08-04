# bug-history/

A record of real bugs found and fixed in this codebase — not a changelog of
features, only genuine defects (crashes, silent failures, wrong behavior).
Added 2026-07-20 after fixing several in one session (Viewgraph
disappearing, the Setting popup silently failing to open, a playblast
writing into the wrong folder) so the same class of mistake doesn't get
reintroduced by a later change that doesn't know this history exists.

**Before changing code in an area that has an entry below, read that entry
first** — most entries end with a "Lesson" describing a pattern to avoid,
not just what happened once. This is the same "read before acting" contract
[GLOSSARY.md](../GLOSSARY.md) has for terminology; root `CLAUDE.md`
references both.

## Index

- [2026-07-20 — Viewgraph disappeared (circular import)](2026-07-20-viewgraph-circular-import.md) — `plugins/core/project_editor/`
- [2026-07-20 — Setting popup silently failed to open](2026-07-20-settings-window-not-opening.md) — `interface/settings/`
- [2026-07-20 — Playblast written into the wrong repo folder after a rename](2026-07-20-repo-path-resolved-from-stale-name.md) — `core/paths.py`, `PublishApi`, `project_editor` (systemic — read this one even if your change is elsewhere)
- [2026-07-20 — Main window not maximizing on launch](2026-07-20-main-window-not-maximizing.md) — `interface/main_window.py`, `launcher.py`
- [2026-07-20 — Playblast wrote into C:\<name> instead of the repo's Custom Path](2026-07-20-playblast-custom-path-leading-slash.md) — `plugins/core/UkoreShotPlayblast/`, `plugins/core/UkoreShot/video_path_store.py`
- [2026-07-20 — Draw overlay never received mouse input (two unrelated root causes)](2026-07-20-draw-overlay-native-video-widget.md) — `plugins/core/UkoreShot/player_widget.py`, `draw_overlay.py`, `plugins/core/DebugConsole/`, `core/extensibility/debug_log.py`
- [2026-07-20 — Repositioning a text box also drew a brush stroke at the same time](2026-07-20-text-tool-drew-strokes-simultaneously.md) — `plugins/core/UkoreShot/draw_overlay.py`, `player_widget.py`
- [2026-07-30 — "Quick Script..." menu item crashed with ModuleNotFoundError: QuickScript](2026-07-30-quickscript-menu-item-dangling-rename.md) — `plugins/core/MayaToolkit/maya-scripts/UkoreMaya/core/menu_utils.py`, `maya-plug-ins/ukoreMaya.py`
- [2026-08-03 — RigPublisher published into C:\<name> instead of the repo's Custom Path](2026-08-03-publishapi-custom-path-leading-slash.md) — `plugins/core/PublishApi/maya-scripts/PublishApi/repo_paths.py` (same leading-slash pattern as the 2026-07-20 entry above — two more unfixed instances flagged, not yet fixed)
- [2026-08-03 — Maya's native "could not find file" dialog still appeared despite `-loadReferenceDepth "none"`](2026-08-03-reference-native-dialog-not-suppressed-by-loadreferencedepth.md) — `plugins/core/maya_launcher/plugin.py` (`_set_project_and_open_command`)

## Adding a new entry

One file per bug, named `YYYY-MM-DD-short-slug.md`, with these sections:

- **Symptom** — what the user actually observed/reported, in their words if useful.
- **Root cause** — the real mechanism, with file:line references.
- **Fix** — what changed and where.
- **Lesson** — the reusable pattern to watch for next time, not just a restatement of the bug. This is the part that actually prevents recurrence — write it for someone who hasn't read the rest of the entry.

Add the new file to the Index above in the same commit.
