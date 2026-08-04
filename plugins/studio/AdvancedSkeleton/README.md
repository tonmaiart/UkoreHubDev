# plugins/studio/AdvancedSkeleton/

AdvancedSkeleton — a vendored Maya rigging toolset, unchanged internal
layout from the original `add-on/AdvancedSkeleton/` (moved to
`plugins/studio/maya_launcher/AdvancedSkeleton/` during the 2026-07-14
consolidation, then split back out to its own top-level plugin here on
2026-07-19 — see `plugins/studio/maya_launcher/README.md` for why).

Like every other Maya tool plugin here, this does **not** launch Maya
itself and has no UI of its own inside UkoreHub — `plugin.py`'s
`register(api)` writes a `PYTHONPATH` contribution (pointing at this
folder's `maya-scripts/`) plus an `ADVANCEDSKELETON_ROOT` contribution
(pointing at `maya-scripts/AdvancedSkeleton/`, the folder containing
`AdvancedSkeleton.mel`) into `plugins/studio/maya_launcher/`'s shared
`maya_launcher_env_bridge` `PluginConfigStore`, read and merged by that
plugin's `open_maya_file` when it actually launches Maya. No direct import
relationship with `maya_launcher` — just the shared `PluginConfigStore` id
convention (see that plugin's README for the full bridge shape).
`RepoToolsStore` (owned by `maya_launcher`) is what lets a studio admin
disable this tool per-repo; this plugin always contributes unconditionally.

`ADVANCEDSKELETON_ROOT` is a single-directory value, not a search-path
list like `PYTHONPATH` — `maya_launcher`'s merge still works for it
unchanged since the prepend-onto-existing logic degrades to "just set it"
when nothing else in the base env already defines that var name.
`plugins/studio/MayaToolkit/maya-scripts/UkoreMaya/core/function.py`'s
`run_advance()`/`run_advance_face()` read this env var at call time (via
`os.environ.get("ADVANCEDSKELETON_ROOT")`) to `mel.eval(source ...)` this
plugin's vendored `.mel` files — so a Maya session launched through
UkoreHub's Maya Launcher always has it, no per-machine env var to set by
hand.
