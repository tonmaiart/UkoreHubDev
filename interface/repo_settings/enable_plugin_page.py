from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QListWidget, QListWidgetItem, QVBoxLayout

from core.extensibility.loader import DiscoveredPlugin, plugin_source
from core.store import LocalConfigStore, MetadataStore
from interface.shared.base_repo_settings_page import BaseRepoSettingsPage

_DESCRIPTION = (
    "Choose which plugins actually apply to this repo. Core plugins (marked "
    "below) are always on — hiding them would remove the only way to do "
    "something this app needs (e.g. switching the active repo at all), not "
    "just an optional feature. Regular plugins default to checked (every "
    "existing repo keeps working unchanged); uncheck one to hide its sidebar "
    "tab for this repo. Opt-in plugins are the opposite: off by default — "
    "check one only if this repo actually needs it. Saved to the shared "
    "Project/Repo registry (Studio)."
)


class EnablePluginPage(BaseRepoSettingsPage):
    """Per-repo toggle for every discovered plugin's sidebar section
    visibility (see MainWindow._apply_plugin_visibility for the full
    three-way precedence this mirrors):
    - manifest.json "core": true (PluginManifest.core) — always checked,
      disabled, never actually hideable regardless of what's persisted.
    - plugins/repo_internal/ or cache/plugins/ (plugin_source() returns
      "repo_internal"/"repo") — opt-in, unchecked by default, persisted to
      Repo.required_plugin_ids. A repo_internal plugin is bundled with the
      app like core; a "repo" plugin is its own separate git clone — both
      get the same opt-in UI treatment here.
    - everything else (plugins/core/ without the core flag) — opt-out,
      checked by default, persisted to Repo.active_plugin_ids, same as
      before repo_internal/cache plugins existed.
    Active-repo resolution + refresh() preamble live in
    BaseRepoSettingsPage (interface/shared/)."""

    def __init__(
        self,
        parent=None,
        *,
        store: MetadataStore,
        local_config_store: LocalConfigStore,
        plugin_catalog: list[DiscoveredPlugin],
    ):
        super().__init__(parent, store=store, local_config_store=local_config_store)
        self._plugin_catalog = plugin_catalog
        self._loading = False

        description_label = QLabel(_DESCRIPTION)
        description_label.setWordWrap(True)

        self.list_widget = QListWidget()
        self.list_widget.itemChanged.connect(self._on_item_changed)

        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(description_label)
        content_layout.addWidget(self.list_widget)

        self.refresh()

    def _on_refresh_content(self) -> None:
        self._rebuild_rows()

    def _rebuild_rows(self) -> None:
        # Guard against itemChanged firing while we're programmatically
        # setting check states below (would otherwise re-persist a
        # half-built list on every single addItem call).
        self._loading = True
        self.list_widget.clear()
        if self._repo is not None:
            active_ids = self._repo.active_plugin_ids
            required_ids = self._repo.required_plugin_ids
            for plugin in self._plugin_catalog:
                is_core = plugin.manifest.core
                is_opt_in = not is_core and plugin_source(plugin) in ("repo_internal", "repo")
                if is_core:
                    checked = True
                    label = f"{plugin.manifest.name} (core — always enabled)"
                elif is_opt_in:
                    checked = plugin.manifest.id in required_ids
                    label = f"{plugin.manifest.name} (opt-in — off until required)"
                else:
                    checked = not active_ids or plugin.manifest.id in active_ids
                    label = plugin.manifest.name
                item = QListWidgetItem(label)
                item.setData(Qt.UserRole, plugin.manifest.id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if is_core:
                    # Rendered checked but not interactive — see
                    # MainWindow._apply_plugin_visibility, which forces a
                    # core plugin's section visible regardless of what ends
                    # up in active_plugin_ids anyway, but this keeps the
                    # persisted list itself honest and the UI from
                    # suggesting a toggle that wouldn't do anything.
                    item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
                self.list_widget.addItem(item)
        self._loading = False

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        if self._loading or self._project is None or self._repo is None:
            return
        opt_in_ids = {
            plugin.manifest.id for plugin in self._plugin_catalog if plugin_source(plugin) in ("repo_internal", "repo")
        }
        checked_ids = {
            self.list_widget.item(row).data(Qt.UserRole)
            for row in range(self.list_widget.count())
            if self.list_widget.item(row).checkState() == Qt.Checked
        }
        # required_plugin_ids (opt-in) is just the checked opt-in ids
        # directly — unlike active_plugin_ids below, "everything checked"
        # here does NOT collapse to [], since an opt-in plugin defaults to
        # off, not on.
        required_ids = [pid for pid in checked_ids if pid in opt_in_ids]
        self.store.set_repo_required_plugin_ids(self._project.id, self._repo.id, required_ids)
        self._repo.required_plugin_ids = required_ids

        non_opt_in_catalog = [p for p in self._plugin_catalog if p.manifest.id not in opt_in_ids]
        active_ids = [pid for pid in checked_ids if pid not in opt_in_ids]
        # Every non-opt-in plugin checked is indistinguishable from
        # "unrestricted" for MainWindow._apply_plugin_visibility, but storing
        # [] explicitly here (rather than the full id list) keeps a
        # brand-new plugin added later auto-enabled for repos that never
        # opted out of anything, matching the "unrestricted by default"
        # behavior.
        if len(active_ids) == len(non_opt_in_catalog):
            active_ids = []
        self.store.set_repo_active_plugin_ids(self._project.id, self._repo.id, active_ids)
        self._repo.active_plugin_ids = active_ids
