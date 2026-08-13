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
to a local executable path on this machine, and click a linked card once
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
- `plugin.py` — everything in one file:
  - `list_installed_programs()` / `_resolve_exe_path()` — best-effort scan
    of Windows' Uninstall registry keys (the same list "Programs and
    Features"/Settings > Apps reads from).
  - `ProgramPickerDialog` — icon+search picker over installed programs.
  - `_ToastNotification` — small self-dismissing `QFrame` popup (`Qt.ToolTip`
    top-level window, `QGraphicsOpacityEffect` + `QPropertyAnimation` fading
    it out after a short hold via `QTimer.singleShot`) used for
    click-to-launch feedback instead of a blocking `QMessageBox` — both the
    "Opening X..." success case and the launch-failed case use it, so
    neither one needs a click to dismiss. Styled via `interface/theme.py`'s
    `QFrame#softwareLinkToast` rule.
  - `_ProgramLinkCard` — one card per linkable (Program, version) slot:
    the Program's own icon (`MetadataStore.resolve_program_icon_path`, falling
    back to a generic icon), name/path/status each on their own line, its
    own "Browse Program...", "Browse Path...", and "Clear" buttons — three
    plain buttons in their own columns (a `QHBoxLayout`), no dropdown/split
    button — no page-level selection state, each card acts on its own
    program directly. Highlights on hover
    (`QFrame#softwareLinkCard:hover` in `interface/theme.py`). **A single
    left-click anywhere on the card itself** (not the buttons — Qt delivers
    the event to whichever child widget is under the cursor first, so the
    buttons still just activate normally) opens the linked executable, or
    opens the same "Browse Program..." picker if nothing is linked yet.
    A linked click first checks
    `api.program_launch_registry.find_launcher(program)`
    (`plugin_api/registries/program_launch_registry.py`) — a plugin
    (currently only `maya_launcher`, its own `cache/plugins/` clone, for
    anything named "maya") can contribute its own launch behavior instead
    of a bare `subprocess.Popen` of the raw linked exe, e.g. Maya's
    setProject/env-merge/force-load-plugins wiring — using whichever repo
    is currently active (`SoftwareLinkerPage.set_repo`'s `repo` param); no
    match, or no active repo, falls back to `subprocess.Popen([exe_path])`
    directly.
  - `SoftwareLinkerPage` — the tab itself: a "Show Only Requirement for
    current repo only" checkbox (checked by default) at the very top of
    the page, the active project's name (read-only), plus a scrollable
    list of `_ProgramLinkCard`s, one per Program Database entry in that
    project. The checkbox narrows that list down to just the active repo's
    `Repo.required_program_ids` — unchecking it goes back to every
    Program in the Project's whole catalog. With no active repo, the
    checkbox has nothing to filter against, so every Program is shown
    regardless of its state (`_rebuild_cards`). Implements the standard
    `SetRepoPage` protocol (`interface/page_protocols.py`) —
    `set_repo(project, repo, workspace_root)` is called whenever this
    becomes the visible section or the active repo changes
    (`interface/main_window.py`'s `_apply_to_current_page` /
    `_apply_set_repo`, optional-protocol per the `ukorehub-interface`
    skill's "Page protocol" section)
    — stores both `project` (which Program Database to list) and `repo`
    (passed through to a matched `ProgramLaunchSpec` on click).
    Auto-detects an unlinked program's executable on every rebuild via the
    full `_resolve_path_for_program` scan below (never overwrites an
    existing link, `_auto_detect_missing`) — always runs automatically now,
    not just a PATH-only check.
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
    **"Auto-Resolve Path" button** (`_on_auto_resolve_path`) still exists as
    a manual re-trigger over the same scan, showing a summary message box
    ("Resolved N program(s)"); never overwrites an existing link, same rule
    as `_auto_detect_missing`.
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
