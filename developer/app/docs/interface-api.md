# interface_api reference

Complete command reference for `app/interface_api/` — the only import
surface `app/launcher.py` and `app/plugin_api/__init__.py` may use to
reach `app/interface/`. Read this instead of opening `app/interface/`
directly; see root `CLAUDE.md`'s rule on this (reading that folder itself
requires the user's explicit permission — an `ask` permission rule in
`.claude/settings.json`). Only open the real source if something you need
genuinely isn't covered here — then update this doc with what you found,
so the next session doesn't need to open it either.

For `app/plugins/core/<Name>/` plugin code specifically, use
[`plugin-api.md`](plugin-api.md) instead — `plugin_api` re-exports every
`interface_api` symbol a plugin needs (shared widgets, theme helpers), and
a plugin file should never import `interface_api` (or `interface`)
directly.

For orientation on what's actually inside `interface/` itself (window
structure, domain folders, `MainWindow`), see [`interface.md`](interface.md)
— this doc only covers the facade surface, not the internals behind it.

## Where this sits

```
interface/      [CLOSED] PySide6 GUI shell — MainWindow, shared widgets,
                 theme, ... Nothing outside interface/ and interface_api/
                 may import interface.* directly.
interface_api/  [FACADE] the only thing allowed to reach into interface/.
                 Flat re-export module — no composition class, since
                 interface/ already has its own (MainWindow).
launcher.py     imports MainWindow/ProjectSelectorDialog/apply_theme/
                 register_builtin_settings_tabs FROM interface_api, calls
                 each at its own existing call site (see "Why not a single
                 composition facade" below).
plugin_api/     imports the shared-widget/theme/LOCAL_REPOSITORY symbols
                 FROM interface_api, re-exporting them to plugins/ (plugins
                 themselves never see interface_api directly — see
                 plugin-api.md).
```

A `launcher.py` or `plugin_api/__init__.py` line should never write `from
interface.xxx import yyy`. Write `from interface_api import yyy` instead.
If something you need isn't re-exported yet, add the re-export to
`interface_api/__init__.py`, then add it to this doc.

## Why not a single composition facade

An earlier draft (external, not implemented) proposed a `UkoreUI` class
bundling `apply_theme` + `register_builtin_settings_tabs` + `MainWindow`
construction into one `__init__`, called once near the end of
`launcher.py`. Rejected — it doesn't match what `launcher.py` actually
does:

- `apply_theme()` runs **before** the `ProjectSelectorDialog` gate (so
  that dialog itself renders themed) — a single bundled facade called
  once, near `MainWindow` construction, would apply the theme *after*
  that dialog might already show.
- `register_builtin_settings_tabs()` runs **before** the plugin-apply
  loop, so a plugin can never silently win a `SettingsTabRegistry` key
  collision against a builtin tab by registering later. Bundling it into
  a facade invoked after plugin discovery would flip that ordering.

`interface_api` is a flat re-export module instead (same shape as
`core_api/__init__.py`) — `launcher.py` keeps calling each piece exactly
where it already does; only the import source changed.

## Re-exported `interface/` symbols

Everything below is importable as `from interface_api import X` — never
`from interface.xxx import X` in `launcher.py` or `plugin_api/__init__.py`.

**App composition** (`interface/main_window.py`, `interface/project_selector_dialog.py`):
`MainWindow`, `ProjectSelectorDialog` — `launcher.py`-only, `plugin_api`
does not re-export these.

**Theme** (`interface/theme.py`, `interface/theme_apply.py`):
`DEFAULT_THEME_NAME`, `get_theme`, `apply_theme` — `apply_theme` is
`launcher.py`-only (applies a Fusion style + a hand-built dark `QPalette` —
see `interface.md`'s Zero QSS Policy section; no custom stylesheet
generation, and no third-party theming library, anymore);
`DEFAULT_THEME_NAME`/`get_theme` are also re-exported via
`plugin_api` (`project_editor/project_graph_view.py`'s HUD overlay/graph
node/edge colors — `ThemeColors` only carries the fields those direct
`QPainter`/`QColor` call sites still need, not a full app-chrome palette).

**Builtin settings wiring**: `register_builtin_settings_tabs`
(`interface/builtin_settings_tabs.py`, `launcher.py`-only) and
`LOCAL_REPOSITORY` (`interface/repo_settings/local_repository_page.py` —
deliberately *not* defined in `builtin_settings_tabs.py` alongside the
other settings-tab key constants, despite being one; see that file's own
comment on why. Also re-exported via `plugin_api` — the
`SettingsTabRegistry` key `project_editor` uses to open the Local
Repository tab from a right-click menu)

**Logging** (`interface/qt_log_handler.py`): `QtLogHandler`,
`configure_app_logging` — `launcher.py`-only for `configure_app_logging`
(called once, right after these imports resolve in `main()`, to attach a
freshly-constructed `QtLogHandler` to the root `logging` logger — see
`developer/app/docs/plugins/DebugConsole.md`); `QtLogHandler` itself is
also re-exported via `plugin_api` (DebugConsole's page type-hints
`api.debug_log_handler` with it).

**Shared widgets** (`interface/shared/`), all also re-exported via
`plugin_api`:
- `widget_helpers.py`: `wrap_scrollable`, `confirm_action`, `show_exclusive`,
  `set_secondary_text`, `set_bold` (the two zero-QSS text-styling helpers —
  see `interface.md`'s Zero QSS Policy section)
- `commit_history.py`: `CommitCard`, `CommitFilesDialog`, `CommitHistoryEntry`,
  `fetch_entries_via_github`, `format_commit_date`, `format_relative_time`
- `image_asset.py`: `pick_image_file`, `save_image_asset`
- `requirements_tree_widget.py`: `RequirementsTreeWidget`

## Import order inside `interface_api/__init__.py` is load-bearing

`interface.main_window` and `interface.builtin_settings_tabs` both
transitively import `plugin_api` (for `UIRegistryManager`/`SettingsTabSpec`/
`CATEGORY_*`), and `plugin_api/__init__.py` imports back from
`interface_api` — a genuine circular dependency between the two facades.
It resolves cleanly (Python allows a partially-initialized module to hand
out names it's already bound) as long as both `__init__.py` files order
their imports so that everything the *other* facade needs is bound before
the import that triggers the cross-load:
- `interface_api/__init__.py` imports every plugin-facing symbol (shared
  widgets, theme, `LOCAL_REPOSITORY`) *before* `interface.builtin_settings_tabs`/
  `interface.main_window` (the two that pull `plugin_api` in).
- `plugin_api/__init__.py` imports its own registries (`CATEGORY_*`,
  `SettingsTabRegistry`, `SettingsTabSpec`, ...) *before* its
  `from interface_api import (...)` block.

Break either ordering and you get `ImportError: cannot import name 'X'
from partially initialized module` — confusing, since the missing name
*is* defined, just not yet at that point in module-load order. This is
also why `LOCAL_REPOSITORY` lives in
`interface/repo_settings/local_repository_page.py` instead of alongside
`COMMON`/`PROGRAM_DATABASE`/etc. in `builtin_settings_tabs.py` — that file
already needs `plugin_api`, so if the constant lived there too,
`interface_api` couldn't re-export it without going through the same
`builtin_settings_tabs` import that triggers the cross-load, defeating the
ordering trick above. Adding a new plugin-facing re-export whose only
home is a module that itself needs `plugin_api` means giving it the same
treatment (a small `plugin_api`-free module of its own) rather than
inlining it into `builtin_settings_tabs.py`.

This only matters for the two `__init__.py` files themselves — real usage
(`launcher.py` importing from `interface_api`, a plugin file importing
from `plugin_api`) always resolves cleanly no matter which one loads
first, since both entry points are exercised in
`developer/app/check_import_boundaries.py`'s effective contract. It would
only break if something outside `interface/`/`interface_api/` imported an
`interface.*` submodule directly instead of going through `interface_api`
— exactly the pattern the closure rule already forbids.

## If this doc is missing something

Add the re-export to `app/interface_api/__init__.py` first (following the
existing pattern — group by source module, add to `__all__`), then add a
row/entry to this doc in the same commit. If a plugin needs the new
symbol too, also add it to `app/plugin_api/__init__.py` and
`plugin-api.md`. Don't have `launcher.py`, `plugin_api/__init__.py`, or a
plugin file import `interface.*` directly as a workaround — that's
exactly the violation `developer/app/check_import_boundaries.py` checks
for.
