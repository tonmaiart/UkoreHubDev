# 2026-08-05 — Maya tool plugins contributed dead paths to the env bridge after moving to `repo_internal/`

## Symptom

User report: enabled `maya_toolkit` + `maya_launcher` for the `AssetTeam`
repo (confirmed in `data/projects.json`'s `required_plugin_ids`), but Maya's
own Plugin Manager never listed `ukoreMaya` as available/loaded at all after
launching Maya through UkoreHub.

## Root cause

Nine Maya-tool plugins under `plugins/repo_internal/` — `MayaToolkit`,
`MayaNgskin`, `UkoreReferenceEditor`, `UkorePlayblast`, `ModelPublisher`,
`RigPublisher`, `PublishApi`, `UkoreBrowser`, `AnimationPublisher` — each
compute their own folder for the shared `maya_launcher_env_bridge`
`PluginConfigStore` contribution (see
`plugins/repo_internal/maya_launcher/README.md`) as
`api.app_root / "plugins" / "core" / "<Name>"` (`AnimationPublisher` had an
even older `"plugins" / "studio" / "AnimationPublisher"`, surviving *two*
renames). Every one of these plugins actually lives under
`plugins/repo_internal/<Name>/` now (moved there 2026-08-04, after starting
in `plugins/studio/` and passing through `plugins/core/`) — the hardcoded
root was never updated at either move.

`plugins/repo_internal/maya_launcher/plugin.py`'s `_build_maya_env`/
`_force_load_plugin_names` both silently skip a contributed path that isn't
a real directory (`if not folder.is_dir(): continue` /
`if not folder.is_dir(): continue`) — by design, so one plugin's bad
contribution can't break env merging for the rest. That meant every one of
these nine plugins' `PYTHONPATH`/`MAYA_PLUG_IN_PATH` contribution silently
evaporated: `import UkoreBrowser`/`PublishApi`/`ModelPublisher`/etc. would
fail inside Maya, `ukoreMaya.py`/ngSkinTools' `.mll` plug-ins were never
even visible in Plugin Manager's list (not just "not loaded" — genuinely not
on `MAYA_PLUG_IN_PATH` at all), regardless of whether the corresponding
plugin was checked under Repository Setting > Enable Plugin.

`data/plugins/core/maya_launcher_env_bridge.json` (the on-disk cache) still
showed the stale `plugins\core\...`/`plugins\studio\...` paths from before
this was caught — but every one of these plugins rewrites its own bridge
entry unconditionally on every app start, so the wrong path was being
freshly reproduced on every launch, not just a leftover from an old build.

## Fix

Each of the nine `plugin.py` files now computes `tool_root =
Path(__file__).resolve().parent` instead of hardcoding
`api.app_root / "plugins" / "<root>" / "<Name>"` — the same
`Path(__file__).resolve().parent` convention `cache/plugins/mGear/plugin.py`
already uses for its own folder lookup (see `plugins/README.md`'s "Multi-file
plugins" section), which is immune to which `plugins/<root>/` a plugin
happens to live under. No manual fix needed for the stale
`maya_launcher_env_bridge.json` cache — it self-heals the next time UkoreHub
starts, since every contributing plugin overwrites its own key
unconditionally at every `register(api)` call.

## Lesson

Any plugin that derives its **own** folder from `api.app_root / "plugins" /
"<root>" / "<Name>"` (instead of `Path(__file__).resolve().parent`) silently
breaks the next time that plugin moves between `plugins/core/`/
`plugins/repo_internal/`/`plugins/studio/` — and because
`core/extensibility/loader.py` never raises and the maya_launcher bridge
silently skips missing folders, there is **no error anywhere** for this: the
plugin loads fine, `register(api)` succeeds, the bridge JSON looks
populated, and the only symptom is a downstream Maya import/Plugin-Manager
failure a studio artist hits days or weeks later. When adding a new
bridge-contributing tool plugin (see that README's "Adding a new nested
tool"), use `Path(__file__).resolve().parent` for `tool_root`, never a
hardcoded `plugins/<root>/<Name>` literal — same class of mistake as
[2026-08-05 — DebugConsole plugin silently failing to load](2026-08-05-debugconsole-stale-plugins-studio-import.md),
just in a shared config value instead of an `import` statement: grep every
plugin's own `.py` files (not just READMEs) for `"plugins" / "core"` /
`"plugins" / "studio"` / `plugins.core.` / `plugins.studio.` literals after
any future `plugins/` root reorganization.
