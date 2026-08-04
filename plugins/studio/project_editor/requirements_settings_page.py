from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout

from core.program_store import ProgramStore
from core.store import LocalConfigStore, MetadataStore
from interface.shared.base_repo_settings_page import BaseRepoSettingsPage
from plugins.studio.project_editor.dialogs import RequirementsTreeWidget


class RequirementsSettingsPage(BaseRepoSettingsPage):
    """Active repo's Requirements tab — the same RequirementsTreeWidget
    RepoDialog shows at Add-Repo time (see dialogs.py), hosted here so an
    *existing* repo's required Programs (+ pinned version for a
    multi-version Program) can be edited too. Repo About (which used to own
    this) was removed 2026-07-20 with no replacement — see developer/GLOSSARY.md's
    "Repo About (removed)" entry — until this tab. Self-persists on every
    check-state change, same convention as every other repo-settings tab
    (EnablePluginPage, Custom Paths, ...) — no separate Save button."""

    def __init__(
        self,
        parent=None,
        *,
        store: MetadataStore,
        local_config_store: LocalConfigStore,
        program_store: ProgramStore,
    ):
        super().__init__(parent, store=store, local_config_store=local_config_store)
        self._program_store = program_store
        self._tree: RequirementsTreeWidget | None = None

        self._content_layout = QVBoxLayout(self.content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

        self.refresh()

    def _on_refresh_content(self) -> None:
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        if self._tree is not None:
            self._content_layout.removeWidget(self._tree)
            self._tree.deleteLater()
            self._tree = None
        if self._repo is None:
            return
        self._tree = RequirementsTreeWidget(
            program_store=self._program_store,
            selected_program_ids=self._repo.required_program_ids,
            selected_program_version_pins=self._repo.program_version_pins,
        )
        self._tree.itemChanged.connect(self._on_tree_changed)
        self._content_layout.addWidget(self._tree)

    def _on_tree_changed(self, _item, _column) -> None:
        if self._project is None or self._repo is None or self._tree is None:
            return
        program_ids = self._tree.selected_program_ids()
        pins = self._tree.selected_program_version_pins()
        self.store.set_repo_requirements(self._project.id, self._repo.id, program_ids)
        self.store.set_repo_program_version_pins(self._project.id, self._repo.id, pins)
        self._repo.required_program_ids = program_ids
        self._repo.program_version_pins = pins
