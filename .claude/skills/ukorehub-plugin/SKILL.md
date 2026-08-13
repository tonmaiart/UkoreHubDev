---
name: ukorehub-plugin
description: Token-scoping discipline for UkoreHub's plugins/ folder (C:\Tonmai\UkoreHub) — when a task names a specific plugin (Explorer, Submit, SoftwareLinker, MayaLauncher, or a new one) or the target path is under plugins/core/<Name>/ or cache/plugins/<Name>/, read and edit ONLY that plugin's own folder — never open a sibling plugin's source as a side effect. Use this for any plugin-specific task even if the user doesn't say "scope" or "context" explicitly; for how plugins are discovered/authored in general see plugins/README.md, and for the plugin discovery mechanics see the ukorehub-core skill.
---

# Working on a single plugin — stay inside its folder

`plugins/core/` and `cache/plugins/` hold
UkoreHub's own sub-systems, sitting side by side (see `plugins/README.md`
for the full authoring guide and what distinguishes the two). Reading
one plugin has **zero information value** for working on a different one,
even though some plugins are larger, multi-file
trees
rather than the single-`plugin.py` shape `software_linker` uses —
`explorer`/`submit` are ordinary multi-file plugins.
`plugins/core/maya_launcher/` itself is small (just the launch/env-merge
logic) — the 7 Maya tools that used to be nested inside it
(`AdvancedSkeleton`, `MayaNgskin`, `MayaToolkit`, `mGear`, `UkoreBrowser`,
`DreamwallPicker`, `StudioLibrary`) are each their own top-level
`plugins/core/<Name>/` plugin as of 2026-07-19, contributing to
`maya_launcher`'s shared `maya_launcher_env_bridge` `PluginConfigStore`
rather than living inside its folder — treat each one as its own separate
plugin for scoping purposes, same as any other `plugins/core/<Name>/`.
`PublishApi/` and `MayaPublisher/` (both now their own `cache/plugins/`
clones, moved out of the removed `plugins/repo_internal/` on 2026-08-10)
are two more plugins in the same family, added 2026-07-19 (the original
`UkorePublisher` was extracted, split into three type-specific plugins,
then those three merged back into one `MayaPublisher` on 2026-08-05) —
same scoping rule applies. Treat every `plugins/core/<Name>/` or
`cache/plugins/<Name>/` as its own
repo for context-budget purposes.

## Rule

1. Identify the one plugin folder the task is actually about
   (`plugins/core/<Name>/` or
   `cache/plugins/<Name>/`).
2. Read that plugin's own `README.md` first if it has one — same
   folder-README convention as `core/README.md`/`interface/README.md` (root
   `CLAUDE.md`). Every plugin should have one; if it doesn't, that's worth
   adding while you're in there, not a reason to skip the step.
3. Read and edit only files inside that plugin's own folder. Do not open a
   sibling plugin's `plugin.py`/other files "just in case" — `explorer/`
   and `submit/` are each 6-8 files; don't read one while working on the
   other just because they sit next to each other in `plugins/core/`.
4. When creating a **new** plugin, don't read an existing one wholesale as
   a copy-paste template. `plugins/README.md` already documents the
   minimum shape (manifest.json + `register(api)`) and the multi-file
   package setup if you need more than one file — read only
   `plugins/core/software_linker/plugin.py` (single-file reference) or
   `plugins/core/explorer/plugin.py` (multi-file reference) depending on
   which shape you're copying, not both.

## Cross-plugin data: convention, not source-reading

If a task genuinely needs another plugin's data or behavior, it's almost
always one of two documented conventions — you need the *convention*, not
the other plugin's source:

- **Shared config data**: the `plugin_config_store` convention — two
  plugins independently constructing a `PluginConfigStore` with the same
  `plugin_id` string, so they share a JSON file with no coupling and no
  import (e.g. `plugins/core/maya_launcher/plugin.py` reading
  `software_linker`'s per-machine `maya.exe` path via
  `api.plugin_config_store("software_linker", shared=False)`). See
  `plugins/README.md`'s "Sharing data with another plugin" section.
- **Cross-plugin UI navigation**: a plain string `SectionRegistry` key
  (e.g. Submit jumping to Explorer's `"repo_browser"` key) plus an
  optional protocol method on the target page (`browse_to_path(path)`,
  same shape as the existing `set_repo()` convention every page
  implements), invoked generically through `UICommandService` — never by
  importing the other plugin's page type. See
  `plugins/core/submit/plugin.py`'s `_wire` for the working example and
  `plugins/README.md`'s "SectionSpec.wire/UICommandService" section.

Reading the *skill or README section* that documents a convention is fine
and expected — reading another plugin's source to reverse-engineer the same
information is the thing to avoid.

## The one real exception: explicit cross-plugin debugging

If the task is genuinely about an interaction between two plugins (e.g.
"why doesn't Submit's Inspect-in-Explorer jump actually scroll to the
file"), that's a cross-plugin task — read both deliberately, because the
task named both. The rule above is about not defaulting to broad
exploration when the task only named one.

## Known pitfalls when authoring/editing a plugin

- **Derive a plugin's own folder via `Path(__file__).resolve().parent`,
  never `api.app_root / "plugins" / "core" / "<Name>"`.** A plugin that
  hardcodes its root this way silently breaks the next time it moves
  between `plugins/core/`, `plugins/repo_internal/` (removed 2026-08-10),
  or a standalone `cache/plugins/` clone — with no error anywhere (the
  loader never raises on this, and anything reading the wrong folder just
  gets an empty/missing result), only a downstream failure days later. This
  bit nine Maya-tool plugins at once during one `plugins/` reorg — after any
  future `plugins/` root reorganization, grep every plugin `.py` file (not
  just READMEs) for `"plugins" / "core"` / `"plugins" / "studio"` literals.
- **After renaming a `plugins/<root>/` directory, grep every plugin's own
  `plugin.py` for the old import literal**, not just READMEs.
  `core/extensibility/loader.py`'s plugin loading never raises — a stale
  `from plugins.<old_root>...` import in one plugin's entry point kills that
  whole plugin with zero visible errors, indefinitely, until someone
  happens to check.
- **A per-user/per-machine cache file belongs under UkoreHub's own
  gitignored `cache/<feature_name>/`, keyed by `Repo.id`** — never written
  into the browsed repo's own working tree. Writing scratch state into a
  production repo silently depends on that repo's own `.gitignore`
  happening to exclude it.
- **Strip leading separators before joining a `CustomPath`-style value onto
  a base directory.** `CustomPath.path` (and similar user-entered relative
  paths) is raw, unsanitized input — pathlib's `/` operator silently
  drive-anchors the result if it starts with `/` or `\`
  (`WindowsPath("C:/repo") / "/movie"` → `"C:/movie"`, silently escaping the
  intended base dir). `.lstrip("/\\")` before any such join. This exact bug
  has recurred independently in more than one plugin — grep for
  `custom_path["path"]`/`repo_paths.py`-style joins before adding a new
  consumer, and don't assume a fix in one plugin covers another.

## Not the same as `interface/`'s window folders

Unlike `interface/`'s window folders (`sidebar/`, `login/`, `about/`,
`settings/`) — where sibling files sometimes share patterns worth seeing,
and a task can legitimately need `interface/main_window.py`'s wiring — a
plugin folder is meant to be fully self-contained apart from the
documented `PluginAPI` surface and the two cross-plugin conventions above.
If a plugin task seems to require reading `interface/main_window.py` or
another plugin's internals beyond those conventions, that's a signal the
task has grown beyond "one plugin" — say so rather than reaching across
silently.
