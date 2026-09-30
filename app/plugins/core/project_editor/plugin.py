from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QStyle

from plugin_api import (
    CATEGORY_GENERAL,
    CATEGORY_PROJECT,
    SectionSpec,
    SettingsTabSpec,
    UICommandService,
    plugin_source,
)
from plugins.core.project_editor.external_plugin_catalog import ExternalPluginCatalog
from plugins.core.project_editor.external_plugin_updater_page import ExternalPluginUpdaterPage
from plugins.core.project_editor.last_check_store import LastCheckedStore
from plugins.core.project_editor.pipeline_store import PipelineStore, migrate_legacy_data
from plugins.core.project_editor.project_editor_page import ProjectEditorPage
from plugins.core.project_editor.project_editor_settings_page import ProjectEditorSettingsPage
from plugins.core.project_editor.sync_status_store import ExternalPluginSyncStatusStore

PLUGIN_ID = "project_editor"
SECTION_KEY = PLUGIN_ID
# One merged Settings tab, replacing the three that used to be registered
# separately here (project_editor_custom_paths / project_editor_project_database /
# project_editor_repo_settings) — merged 2026-09-01 per the user's own
# request, after they hand-merged the three .ui files those pages loaded
# into one ProjectEditorSettingsWindow.ui. See project_editor_settings_page.py.
SETTINGS_KEY = "project_editor_settings"
EXTERNAL_PLUGINS_UPDATER_SETTINGS_KEY = "external_plugins_updater"

# The External Plugins catalog's own storage plugin_id — used as the key
# for api.project_plugin_config_store()/api.plugin_config_store() so this
# plugin's catalog CRUD (Project Database tab) and
# "Plugins" status tab all read/write the exact same
# Project.plugin_data["external_plugins"]["catalog"] data every existing
# machine/project already has on disk — kept unchanged from
# ExternalPluginManager's own PLUGIN_ID (that plugin was merged into this
# one 2026-09-01, see external_plugin_catalog.py's own docstring) rather
# than renamed to "project_editor", which would've orphaned every existing
# catalog/status/last-check record.
_EXTERNAL_PLUGINS_PLUGIN_ID = "external_plugins"


def _backfill_catalog_plugin_ids(api, catalog: ExternalPluginCatalog) -> None:
    """Fills in CatalogEntry.plugin_id for any entry this session's
    discovered plugins already reveal (matched by folder_name) — Portal's
    clone-if-missing (portal/plugin_update.py) can only map a repo's
    required manifest ids back to a catalog entry once this is set."""
    discovered_by_folder = {
        plugin.dir_path.name: plugin for plugin in api.plugin_catalog if plugin_source(plugin) == "repo"
    }
    for entry in catalog.list_entries():
        if entry.plugin_id:
            continue
        discovered = discovered_by_folder.get(entry.folder_name)
        if discovered is not None:
            catalog.update_plugin_id(entry.id, discovered.manifest.id)


# plugins/core/submit's own SectionRegistry key — a literal string, not an
# import, so this plugin's register(api) doesn't fail to load if Submit's
# plugin were ever missing/broken (same convention submit/plugin.py itself
# uses for Explorer's "repo_browser" key).
_SUBMIT_SECTION_KEY = "repo_git_status"


def _wire(page: ProjectEditorPage, host: UICommandService) -> None:
    page.bind_set_active_repo(host.set_active_repo)
    # navigate_and_focus's `path` argument only matters to a page that
    # implements PathFocusablePage (interface/page_protocols.py) — Submit's
    # RepoGitStatusPage doesn't, so this just switches the tab; the empty
    # Path is a harmless placeholder that's never read.
    page.bind_navigate_to_submit(lambda: host.navigate_and_focus(_SUBMIT_SECTION_KEY, Path()))


def register(api) -> None:
    migrate_legacy_data(api)
    pipeline_store = PipelineStore(api.metadata, api.project_plugin_config_store(PLUGIN_ID))
    page = ProjectEditorPage(
        store=api.metadata,
        local_config_store=api.local_config,
        pipeline_store=pipeline_store,
        git_service=api.git,
    )
    api.register_section(
        SectionSpec(
            key=SECTION_KEY,
            label="Project Editor",
            order=5,
            page_factory=lambda: page,
            wire=_wire,
            standard_icon=QStyle.SP_FileDialogListView,
        )
    )
    # One ExternalPluginCatalog instance, shared by CRUD (this settings tab,
    # below) and the "Plugins" status tab (further below) — both read/write
    # the exact same Project.plugin_data["external_plugins"]["catalog"].
    external_plugin_catalog = ExternalPluginCatalog(api.project_plugin_config_store(_EXTERNAL_PLUGINS_PLUGIN_ID))
    api.register_settings_tab(
        SettingsTabSpec(
            key=SETTINGS_KEY,
            label="Project Editor Settings",
            order=15,
            page_factory=lambda: ProjectEditorSettingsPage(
                store=api.metadata,
                local_config_store=api.local_config,
                pipeline_store=pipeline_store,
                catalog=external_plugin_catalog,
                plugin_catalog=api.plugin_catalog,
                add_repo=page.add_repo,
                rename_repo=page.rename_repo,
                delete_repo=page.delete_repo,
                git_service=api.git,
                plugins_root=api.cache_dir / "plugins",
            ),
            on_activated=lambda widget: widget.refresh(),
            category=CATEGORY_PROJECT,
        )
    )

    # Updating/cloning cache/plugins/ entries happens in Portal before the
    # app starts (portal/plugin_update.py) — plugins only load once at
    # startup, so doing it in here could only ever end in a restart prompt.
    # What's left in-app is the manual Settings > Account > Plugins tab.
    api.on_app_start(lambda _context: _backfill_catalog_plugin_ids(api, external_plugin_catalog))
    external_plugins_local_store = api.plugin_config_store(_EXTERNAL_PLUGINS_PLUGIN_ID, shared=False)
    sync_status_store = ExternalPluginSyncStatusStore(external_plugins_local_store)
    last_check_store = LastCheckedStore(external_plugins_local_store)
    api.register_settings_tab(
        SettingsTabSpec(
            key=EXTERNAL_PLUGINS_UPDATER_SETTINGS_KEY,
            label="Plugins",
            order=10,
            page_factory=lambda: ExternalPluginUpdaterPage(
                git_service=api.git,
                plugins_root=api.cache_dir / "plugins",
                catalog=external_plugin_catalog,
                plugin_catalog=api.plugin_catalog,
                sync_status_store=sync_status_store,
                last_check_store=last_check_store,
            ),
            category=CATEGORY_GENERAL,
        )
    )
