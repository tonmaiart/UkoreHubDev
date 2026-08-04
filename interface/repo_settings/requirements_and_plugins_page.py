from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout

from core.extensibility.loader import DiscoveredPlugin, plugin_source
from core.program_store import ProgramStore
from core.store import LocalConfigStore, MetadataStore
from interface.shared.base_repo_settings_page import BaseRepoSettingsPage
from interface.shared.requirements_tree_widget import RequirementsTreeWidget

_PLUGIN_DESCRIPTION = (
    "Choose which plugins actually apply to this repo. Core plugins are "
    "always on — hiding them would remove functionality this app needs "
    "everywhere (e.g. switching the active repo at all), not just an "
    "optional feature — so there's nothing to toggle. Internal and "
    "External plugins are opt-in: off by default, check one only if this "
    "repo actually needs it. Saved to the shared Project/Repo registry "
    "(Studio)."
)


class RequirementsAndPluginsPage(BaseRepoSettingsPage):
    """Active repo's "Requirements & Plugins" tab — merges what used to be
    two separate CATEGORY_REPO tabs (Requirements, owned by
    plugins/core/project_editor/, and Enable Plugin, owned by this folder)
    into one, per the user's 2026-08-04 request. Two sections stacked
    vertically:
    - Program Requirements — the same RequirementsTreeWidget RepoDialog
      shows at Add-Repo time (interface/shared/requirements_tree_widget.py),
      hosted here so an *existing* repo's required Programs (+ pinned
      version for a multi-version Program) can be edited too.
    - Enable Plugin — every discovered plugin's sidebar section visibility,
      split into three lists by core.extensibility.loader.plugin_source()
      instead of one flat checklist (see MainWindow._apply_plugin_visibility
      for the full precedence this mirrors):
      - Core (plugins/core/) — always on for every repo, no checkbox and no
        per-repo opt-out (2026-08-04): anything left in plugins/core/ is
        meant to be universal app-level functionality now that anything
        repo-specific (Maya tools, ...) lives under repo_internal/ instead.
      - Internal (plugins/repo_internal/) — opt-in, unchecked by default,
        persisted to Repo.required_plugin_ids.
      - External (cache/plugins/, its own separate git clone) — opt-in,
        same as Internal, same Repo.required_plugin_ids list.
    Self-persists on every check-state change, same convention as every
    other repo-settings tab — no separate Save button. Active-repo
    resolution + refresh() preamble live in BaseRepoSettingsPage
    (interface/shared/)."""

    def __init__(
        self,
        parent=None,
        *,
        store: MetadataStore,
        local_config_store: LocalConfigStore,
        program_store: ProgramStore,
        plugin_catalog: list[DiscoveredPlugin],
    ):
        super().__init__(parent, store=store, local_config_store=local_config_store)
        self._program_store = program_store
        self._plugin_catalog = plugin_catalog
        self._requirements_tree: RequirementsTreeWidget | None = None
        self._loading_plugins = False

        self._requirements_group = QGroupBox("Program Requirements")
        self._requirements_layout = QVBoxLayout(self._requirements_group)

        plugin_description = QLabel(_PLUGIN_DESCRIPTION)
        plugin_description.setWordWrap(True)

        self._core_list = QListWidget()
        self._internal_list = QListWidget()
        self._internal_list.itemChanged.connect(self._on_plugin_item_changed)
        self._external_list = QListWidget()
        self._external_list.itemChanged.connect(self._on_plugin_item_changed)

        core_group = QGroupBox("Core Plugin")
        core_layout = QVBoxLayout(core_group)
        core_layout.addWidget(self._core_list)

        internal_group = QGroupBox("Internal Plugin")
        internal_layout = QVBoxLayout(internal_group)
        internal_layout.addWidget(self._internal_list)

        external_group = QGroupBox("External Plugin")
        external_layout = QVBoxLayout(external_group)
        external_layout.addWidget(self._external_list)

        plugin_group = QGroupBox("Enable Plugin")
        plugin_layout = QVBoxLayout(plugin_group)
        plugin_layout.addWidget(plugin_description)
        plugin_layout.addWidget(core_group)
        plugin_layout.addWidget(internal_group)
        plugin_layout.addWidget(external_group)

        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._requirements_group)
        content_layout.addWidget(plugin_group)

        self.refresh()

    def _on_refresh_content(self) -> None:
        self._rebuild_requirements_tree()
        self._rebuild_plugin_lists()

    def _rebuild_requirements_tree(self) -> None:
        if self._requirements_tree is not None:
            self._requirements_layout.removeWidget(self._requirements_tree)
            self._requirements_tree.deleteLater()
            self._requirements_tree = None
        if self._repo is None:
            return
        self._requirements_tree = RequirementsTreeWidget(
            program_store=self._program_store,
            selected_program_ids=self._repo.required_program_ids,
            selected_program_version_pins=self._repo.program_version_pins,
        )
        self._requirements_tree.itemChanged.connect(self._on_requirements_tree_changed)
        self._requirements_layout.addWidget(self._requirements_tree)

    def _on_requirements_tree_changed(self, _item, _column) -> None:
        if self._project is None or self._repo is None or self._requirements_tree is None:
            return
        program_ids = self._requirements_tree.selected_program_ids()
        pins = self._requirements_tree.selected_program_version_pins()
        self.store.set_repo_requirements(self._project.id, self._repo.id, program_ids)
        self.store.set_repo_program_version_pins(self._project.id, self._repo.id, pins)
        self._repo.required_program_ids = program_ids
        self._repo.program_version_pins = pins

    def _rebuild_plugin_lists(self) -> None:
        # Guard against itemChanged firing while we're programmatically
        # setting check states below (would otherwise re-persist a
        # half-built list on every single addItem call).
        self._loading_plugins = True
        self._core_list.clear()
        self._internal_list.clear()
        self._external_list.clear()
        if self._repo is not None:
            required_ids = self._repo.required_plugin_ids
            for plugin in self._plugin_catalog:
                source = plugin_source(plugin)
                if source == "core":
                    self._core_list.addItem(QListWidgetItem(plugin.manifest.name))
                    continue
                target_list = self._internal_list if source == "repo_internal" else self._external_list
                item = QListWidgetItem(plugin.manifest.name)
                item.setData(Qt.UserRole, plugin.manifest.id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if plugin.manifest.id in required_ids else Qt.Unchecked)
                target_list.addItem(item)
        self._loading_plugins = False

    def _on_plugin_item_changed(self, _item: QListWidgetItem) -> None:
        if self._loading_plugins or self._project is None or self._repo is None:
            return
        required_ids = [
            self._internal_list.item(row).data(Qt.UserRole)
            for row in range(self._internal_list.count())
            if self._internal_list.item(row).checkState() == Qt.Checked
        ] + [
            self._external_list.item(row).data(Qt.UserRole)
            for row in range(self._external_list.count())
            if self._external_list.item(row).checkState() == Qt.Checked
        ]
        self.store.set_repo_required_plugin_ids(self._project.id, self._repo.id, required_ids)
        self._repo.required_plugin_ids = required_ids
