# plugins/core/software_linker/

Moved here (2026-08-13) from `app/plugins/core/software_linker/README.md`.
See `plugins-guide.md` for the general plugin-authoring conventions this
plugin follows.

Registers the sidebar's **"Program Launcher"** tab (icon
`QStyle.SP_ComputerIcon` — built-in Qt icon, not a bundled bitmap, see
`interface.md`'s Zero QSS Policy section — order 40, after Explorer=10/Submit=20/
project_editor=15) — lets the user link each Program Database entry (each
Project's own `Project.programs`, `core/models.py` — not shared across
Projects, see `core_api`'s `MetadataStore.list_programs`/`get_program`)
to a local executable path on this machine, and double-click a linked row
to open it. Per-machine data, since "what's installed here" is never
team-shared. As of 2026-08-10 this replaced the old `software_linker`
**Settings tab** (`api.register_settings_tab`) — moved wholesale to a
top-level `SectionSpec` instead — and absorbed the retired
`program_launcher` plugin's launch behavior the same day; `PLUGIN_ID`
stays the literal string `"software_linker"` regardless, since other
plugins read the same `PluginConfigStore` id (see below), independent of
the tab's own label. A single-file plugin (unlike `plugins/core/explorer/`/
`submit/`, which are multi-file — see `plugins-guide.md`'s "Multi-file
plugins" section for why that's a different setup).

- `manifest.json` — plugin id `software_linker`, entry point `plugin.py`.
- `ProgramLauncherWindow.ui` — Qt Designer source for the whole tab (the
  `listWidget_program_list` list plus `checkBox_ShowOnlyRequirement` and
  the `pushButton_auto_resolve`/`pushButton_browse_path`/
  `pushButton_browse_program`/`pushButton_clear_link_path` buttons).
  `SoftwareLinkerPage.__init__` loads this at runtime via `QUiLoader`
  instead of building the layout in code — same convention as
  `plugins/core/explorer/browser_widget.py`'s `explorer_section.ui` — and
  binds each widget with `self.ui.findChild(Type, "objectName")`.
  Renaming an `objectName` in the `.ui` breaks that binding with no error
  at import time (`findChild` just returns `None`), so keep the two in
  sync.
- `plugin.py` — everything else in one file:
  - `list_installed_programs()` / `_resolve_exe_path()` — best-effort scan
    of Windows' Uninstall registry keys (the same list "Programs and
    Features"/Settings > Apps reads from).
  - `ProgramPickerDialog` — icon+search picker over installed programs
    (its own small dialog, built in code — not covered by
    `ProgramLauncherWindow.ui`).
  - `SoftwareLinkerPage` — the tab itself, one `QListWidgetItem` per
    linkable (Program, version) slot in `listWidget_program_list` (built
    by `_rebuild_list`), instead of the one-card-per-program layout this
    plugin used before 2026-08-19. Each item's icon is the Program's own
    (`MetadataStore.resolve_program_icon_path`, falling back to a generic
    icon); its two-line text is `"{label}\n{linked_path}"` when linked or
    `"{label}\nNot linked"` otherwise (`_apply_item_state`) — bold text
    (`QFont.setBold`) plus normal `QPalette.Text` when linked, regular
    weight plus `QPalette.PlaceholderText` when not, both plain
    `QPalette`/`QFont` calls with no `interface/` import and no
    plugin-specific rule in `interface/theme.py` to keep in sync (the
    retired `_ProgramLinkCard`/`_ToastNotification` classes used
    `interface/shared/widget_helpers.py`'s `set_bold`/`set_secondary_text`
    plus a `QFrame#softwareLinkCard`/`QFrame#softwareLinkToast` pair of
    QSS rules in `interface/theme.py` — both gone now, along with those
    two rules, which are worth deleting from `interface/theme.py`
    separately since editing `interface/` needs its own permission ask).
    No page-level selection state beyond `QListWidget`'s own
    `currentItem()` — the "Browse Program...", "Browse Path...", and
    "Clear Link Path" buttons act on whichever row is currently selected
    (`_selected_row`), and are disabled via `_update_action_buttons_enabled`
    whenever nothing is selected. **Double-clicking a row**
    (`_on_item_double_clicked`, replacing the old single-left-click-anywhere-
    on-the-card behavior) opens the linked executable, or opens the same
    "Browse Program..." picker if nothing is linked yet. Launch feedback
    (`"Opening X..."` / a launch-failure message) is a plain
    `QToolTip.showText` call instead of the old custom-animated toast
    popup — nothing to click through, and no styling dependency on
    `interface/theme.py`. A linked double-click first checks
    `api.program_launch_registry.find_launcher(program)`
    (`plugin_api/registries/program_launch_registry.py`) — a plugin
    (currently only `maya_launcher`, its own `cache/plugins/` clone, for
    anything named "maya") can contribute its own launch behavior instead
    of a bare `subprocess.Popen` of the raw linked exe, e.g. Maya's
    setProject/env-merge/force-load-plugins wiring — using whichever repo
    is currently active (`SoftwareLinkerPage.set_repo`'s `repo` param); no
    match, or no active repo, falls back to `subprocess.Popen([exe_path])`
    directly. The "Show Only Requirement for current repo only" checkbox
    (checked by default) narrows the list down to just the active repo's
    `Repo.required_program_ids` — unchecking it goes back to every Program
    in the Project's whole catalog. With no active repo, the checkbox has
    nothing to filter against, so every Program is shown regardless of its
    state (`_rebuild_list`). Implements the standard `SetRepoPage` protocol
    (`interface/page_protocols.py`) — `set_repo(project, repo,
    workspace_root)` is called whenever this becomes the visible section or
    the active repo changes (`interface/main_window.py`'s
    `_apply_to_current_page` / `_apply_set_repo`, optional-protocol per the
    `ukorehub-interface` skill's "Page protocol" section) — stores both
    `project` (which Program Database to list) and `repo` (passed through
    to a matched `ProgramLaunchSpec` on double-click). `_rebuild_list`
    preserves the current selection across a rebuild by key (`previous_key`
    → `restore_item`) since `QListWidget.clear()` otherwise drops it.
    Auto-detects an unlinked program's executable on every rebuild via the
    full `_resolve_path_for_program` scan below (never overwrites an
    existing link, `_auto_detect_missing`) — always runs automatically now,
    not just a PATH-only check. This tab no longer shows the active
    project's name as a standalone label — `ProgramLauncherWindow.ui` has
    no widget for it; add one to the `.ui` (and a matching
    `self.ui.findChild` bind) if that's needed again.
  - `_resolve_path_for_program` — the shared three-source scan, tried in
    order until one hits:
    1. System PATH (`shutil.which`).
    2. The Windows Uninstall registry (`list_installed_programs`), matched
       by substring against the Program's own name.
    3. A small hardcoded table of default install locations for common
       DCCs (`_DEFAULT_INSTALL_GLOBS` — Maya, Unreal, Blender, Photoshop),
       glob-matched since the version number is baked into the install
       folder name.

    Runs automatically for every still-unlinked Program on each rebuild
    (`_auto_detect_missing`) — no longer gated behind an explicit click.
    **"Auto Resolve to Unlink Path" button** (`pushButton_auto_resolve` →
    `_on_auto_resolve_path`) still exists as a manual re-trigger over the
    same scan, showing a summary message box ("Resolved N program(s)");
    never overwrites an existing link, same rule as `_auto_detect_missing`.
  - `register(api)` — registers `SoftwareLinkerPage` as a top-level
    `SectionSpec` via `api.register_section(...)`. The page's
    `config_store` is `api.plugin_config_store(PLUGIN_ID, shared=False)` —
    per-machine, keyed by Program id. **Other plugins read this same
    mapping** by calling `api.plugin_config_store("software_linker",
    shared=False)` themselves (e.g. `maya_launcher`'s `plugin.py`
    reading a linked `maya.exe` path) — no coupling API needed, just
    agreeing on the `"software_linker"` id string. See
    `plugins-guide.md`'s "Sharing data with another plugin" section.

## `plugin_api/registries/program_launch_registry.py` note

This plugin is the sole consumer of `ProgramLaunchRegistry`/
`find_launcher()` again (it was orphaned briefly between the retired
`program_launcher` plugin and this plugin picking up click-to-launch the
same day) — `maya_launcher`'s (its own `cache/plugins/` clone) `plugin.py`'s
`launch_maya_standalone` is still the only contributed spec.
If this plugin's click-to-launch is ever removed too, check whether
`plugin_api/registries/program_launch_registry.py`, its `plugin_api.py`/`launcher.py`
wiring, and `maya_launcher`'s `launch_maya_standalone` registration have
become dead code again before leaving them in place.

**Working here:** stay inside this folder unless the change needs a new
`core_api` primitive or touches `plugin_api/registries/section_registry.py`'s wiring.
