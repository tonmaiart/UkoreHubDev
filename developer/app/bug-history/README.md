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
- [2026-08-04 — Logout crashed UkoreHub.exe with "Failed to load Python DLL"](2026-08-04-relaunch-inherits-pyinstaller-onefile-env.md) — `interface/main_window.py` (`_relaunch_to_login`), inherited PyInstaller onefile bootloader env vars
- [2026-08-05 — Explorer's Last Opened Files list got committed into browsed repos](2026-08-05-explorer-last-opened-committed-to-browsed-repo.md) — `plugins/core/explorer/last_opened_store.py`, `browser_widget.py`
- [2026-08-05 — DebugConsole plugin silently failing to load (stale `plugins.studio` import)](2026-08-05-debugconsole-stale-plugins-studio-import.md) — `plugins/core/DebugConsole/plugin.py`
- [2026-08-05 — Maya tool plugins contributed dead paths to the env bridge after moving to `repo_internal/`](2026-08-05-maya-bridge-tools-hardcoded-stale-plugins-core-root.md) — `plugins/repo_internal/{MayaToolkit,MayaNgskin,UkoreReferenceEditor,UkorePlayblast,ModelPublisher,RigPublisher,PublishApi,UkoreBrowser,AnimationPublisher}/plugin.py` (systemic — read this one even if your change is to just one of these)
- [2026-08-05 — QuickData.py crashed the whole MayaToolkit plugin when ngSkinTools2 wasn't installed](2026-08-05-quickdata-hardcoded-ngskintools-import.md) — `plugins/repo_internal/MayaToolkit/maya-scripts/tmlib/core/QuickData.py`, `WeightPuller/interface.py`
- [2026-08-05 — Ukore Reference Editor's Repath button couldn't pick a file, only a folder](2026-08-05-repath-filemode2-native-dialog-directory-only.md) — `plugins/repo_internal/UkoreReferenceEditor/maya-scripts/UkoreReferenceEditor/interface.py`
- [2026-08-05 — Ukore Reference Editor's auto-redirect/auto-load never ran for the very first Launch-triggered scene open](2026-08-05-reference-editor-callback-registered-too-late-for-first-open.md) — `plugins/repo_internal/MayaToolkit/maya-plug-ins/ukoreMaya.py` (`initializePlugin`)
- [2026-08-08 — UkoreHub.exe self-update failed with "unable to unlink old 'UkoreHub.exe'"](2026-08-08-self-update-locked-own-exe.md) — was `developer/packaging/updater.py` (`ensure_up_to_date`); as of 2026-08-09 that file lives in the separate `UkoreHubLauncher` repo, and the entry's "Update" section covers the repo split that removed the root cause for ordinary app releases
- [2026-08-08 — External Plugins' "Stage Untracked & Push" nearly staged/pushed the whole UkoreHub app repo into a repo plugin's remote](2026-08-08-external-plugins-broken-git-dir-resolved-to-app-repo.md) — `plugins/core/ExternalPlugins/`, `core/git_service.py` (`is_repo_root`)
- [2026-08-09 — UkoreHub auto-update failed: "local changes to data/projects.json would be overwritten by merge"](2026-08-09-shared-data-git-pull-conflict.md) — `developer/packaging/updater.py`, `core/store.py`, `core/program_store.py` (fixed by moving shared JSON stores off git onto Google Cloud Storage — see `core/cloud_sync.py`)
- [2026-08-09 — Self-update kept failing on the same "would be overwritten by merge" error even after the fix above](2026-08-09-self-update-pull-still-blocked-during-cutover.md) — `developer/packaging/updater.py`, `core/self_update.py` (the one pull that crosses from "still tracked" to "no longer tracked" hits the identical conflict, forever, on any machine not yet past it — read this one even if you think the entry above already covers it)
- [2026-08-09 — Two Maya-side scripts silently lost the active repo after `local_config.json` moved to `cache/`](2026-08-09-maya-scripts-stale-data-local-config-path.md) — `plugins/repo_internal/PublishApi/maya-scripts/PublishApi/repo_paths.py`, `plugins/repo_internal/UkoreReferenceEditor/maya-scripts/UkoreReferenceEditor/repo_paths.py`
- [2026-08-09 — Switching to DebugConsole or BananaSketch crashed with `AttributeError: ... has no attribute 'set_repo'`](2026-08-09-set-repo-not-optional-protocol-method.md) — `interface/main_window.py` (`_apply_to_current_page`, `_apply_to_persistent_pages`)
- [2026-08-10 — External Plugins' per-project filter silently emptied Requirements & Plugins' External list for existing catalog entries](2026-08-10-external-plugins-project-filter-orphaned-existing-entries.md) — `plugins/core/ExternalPlugins/`, `interface/repo_settings/requirements_and_plugins_page.py`
- [2026-08-10 — External Plugins catalog page showed no entries after adding them, even though Requirements & Plugins showed them fine](2026-08-10-external-plugins-stale-shared-catalog-cache.md) — `plugins/core/ExternalPlugins/catalog_store.py`, `core/vcs/cloud_sync.py` (systemic — any long-lived `PluginConfigStore(shared=True)` is at risk, read even if your change is elsewhere)
- [2026-08-10 — External Plugins page/auto-sync engine pointed at `app/cache/plugins` instead of the real `cache/plugins`](2026-08-10-external-plugins-plugins-root-used-app-root-not-cache-dir.md) — `plugins/core/ExternalPlugins/plugin.py` (pre-existing bug, not specific to this plugin — read before deriving a cache/plugins-style path from `api.app_root` anywhere)
- [2026-08-11 — Remaining `resolve_repo_path`-from-name call sites fixed (completes 2026-07-20 entry)](2026-08-11-resolve-repo-path-stale-name-remaining-callers-fixed.md) — `interface/main_window.py`, `interface/repo_settings/local_repository_page.py`, `plugins/core/explorer/repo_browser_page.py`, `plugins/core/submit/repo_git_status_page.py`

## Adding a new entry

One file per bug, named `YYYY-MM-DD-short-slug.md`, with these sections:

- **Symptom** — what the user actually observed/reported, in their words if useful.
- **Root cause** — the real mechanism, with file:line references.
- **Fix** — what changed and where.
- **Lesson** — the reusable pattern to watch for next time, not just a restatement of the bug. This is the part that actually prevents recurrence — write it for someone who hasn't read the rest of the entry.

Add the new file to the Index above in the same commit.
