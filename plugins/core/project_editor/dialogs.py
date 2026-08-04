from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from core.program_store import ProgramStore
from interface.shared.image_asset import pick_image_file

_NODE_KIND_ROLE = Qt.UserRole + 1


class RequirementsTreeWidget(QTreeWidget):
    """Each Program is a checkable top-level node (check = required), with
    a checkable child per version for a multi-version Program (pin, radio-
    style). Used by RepoDialog (repo creation)."""

    def __init__(
        self,
        parent=None,
        *,
        program_store: ProgramStore,
        selected_program_ids: list[str] | None = None,
        selected_program_version_pins: dict[str, str] | None = None,
    ):
        super().__init__(parent)
        self.setHeaderHidden(True)

        selected_program_id_set = set(selected_program_ids or [])
        version_pins = selected_program_version_pins or {}

        for program in program_store.list_programs():
            version_suffix = f" (v{', '.join(program.versions)})" if program.versions else ""
            program_item = QTreeWidgetItem([f"{program.name}{version_suffix}"])
            program_item.setFlags(program_item.flags() | Qt.ItemIsUserCheckable)
            program_item.setCheckState(0, Qt.Checked if program.id in selected_program_id_set else Qt.Unchecked)
            program_item.setData(0, Qt.UserRole, program.id)
            program_item.setData(0, _NODE_KIND_ROLE, "program")
            icon_path = program_store.resolve_icon_path(program)
            if icon_path and icon_path.exists():
                program_item.setIcon(0, QIcon(str(icon_path)))
            if len(program.versions) > 1:
                pinned = version_pins.get(program.id)
                default_version = pinned if pinned in program.versions else program.versions[0]
                for version in program.versions:
                    version_item = QTreeWidgetItem([version])
                    version_item.setFlags(version_item.flags() | Qt.ItemIsUserCheckable)
                    version_item.setCheckState(0, Qt.Checked if version == default_version else Qt.Unchecked)
                    version_item.setData(0, Qt.UserRole, version)
                    version_item.setData(0, _NODE_KIND_ROLE, "version")
                    program_item.addChild(version_item)
            self.addTopLevelItem(program_item)
            program_item.setExpanded(True)

        self.itemChanged.connect(self._on_tree_item_changed)

    def _on_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        kind = item.data(0, _NODE_KIND_ROLE)
        if kind == "version" and item.checkState(0) == Qt.Checked:
            # Version children under one Program are exclusive (radio-style)
            # — picking one is the repo's pin, so uncheck any other version
            # sibling.
            parent = item.parent()
            if parent is None:
                return
            for i in range(parent.childCount()):
                sibling = parent.child(i)
                if (
                    sibling is not item
                    and sibling.data(0, _NODE_KIND_ROLE) == "version"
                    and sibling.checkState(0) == Qt.Checked
                ):
                    sibling.setCheckState(0, Qt.Unchecked)

    def selected_program_ids(self) -> list[str]:
        selected = []
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, _NODE_KIND_ROLE) == "program" and item.checkState(0) == Qt.Checked:
                selected.append(item.data(0, Qt.UserRole))
        return selected

    def selected_program_version_pins(self) -> dict[str, str]:
        pins: dict[str, str] = {}
        for i in range(self.topLevelItemCount()):
            program_item = self.topLevelItem(i)
            if program_item.data(0, _NODE_KIND_ROLE) != "program":
                continue
            program_id = program_item.data(0, Qt.UserRole)
            for j in range(program_item.childCount()):
                child = program_item.child(j)
                if child.data(0, _NODE_KIND_ROLE) == "version" and child.checkState(0) == Qt.Checked:
                    pins[program_id] = child.data(0, Qt.UserRole)
                    break
        return pins


class ProjectDialog(QDialog):
    def __init__(self, parent=None, *, name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Edit Project" if name else "Add Project")

        self.name_edit = QLineEdit(name)

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        self.accept()

    def name(self) -> str:
        return self.name_edit.text().strip()


class RepoDialog(QDialog):
    """Full Name/URL/Thumbnail/Requirements editor, used as-is for **Add**
    Repo (one-step bootstrap of a new repo record). For **editing** an
    existing repo, Project Editor's node context menu now only asks for
    Name/Git URL here (show_thumbnail=False, no program_store) — Thumbnail
    has its own "Change Thumbnail..." context menu action; editing
    Requirements on an existing repo has no UI entry point since Repo About
    was removed."""

    def __init__(
        self,
        parent=None,
        *,
        name: str = "",
        git_url: str = "",
        show_thumbnail: bool = True,
        thumbnail_path: Path | None = None,
        program_store: ProgramStore | None = None,
        selected_program_ids: list[str] | None = None,
        selected_program_version_pins: dict[str, str] | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Edit Repo" if name else "Add Repo")
        self._chosen_thumbnail_path: Path | None = None

        self.name_edit = QLineEdit(name)
        self.git_url_edit = QLineEdit(git_url)
        self.git_url_edit.setPlaceholderText("git@github.com:org/repo.git")

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Git URL:", self.git_url_edit)

        self.thumbnail_preview: QLabel | None = None
        if show_thumbnail:
            self.thumbnail_preview = QLabel("No image")
            self.thumbnail_preview.setFixedSize(120, 68)
            self.thumbnail_preview.setScaledContents(True)
            if thumbnail_path and thumbnail_path.exists():
                self.thumbnail_preview.setPixmap(QPixmap(str(thumbnail_path)))
            choose_image_btn = QPushButton("Choose Image...")
            choose_image_btn.clicked.connect(self._on_choose_image)
            thumbnail_row = QHBoxLayout()
            thumbnail_row.addWidget(self.thumbnail_preview)
            thumbnail_row.addWidget(choose_image_btn)
            form.addRow("Thumbnail:", thumbnail_row)

        # See RequirementsTreeWidget for the tree shape (checkable Program
        # nodes with checkable per-version children).
        self.requirements_tree: RequirementsTreeWidget | None = None
        if program_store is not None:
            self.requirements_tree = RequirementsTreeWidget(
                program_store=program_store,
                selected_program_ids=selected_program_ids,
                selected_program_version_pins=selected_program_version_pins,
            )
            form.addRow("Requirements:", self.requirements_tree)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_choose_image(self) -> None:
        file_path = pick_image_file(self, "Choose Thumbnail Image")
        if file_path is None:
            return
        self._chosen_thumbnail_path = file_path
        self.thumbnail_preview.setPixmap(QPixmap(str(file_path)))

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip() or not self.git_url_edit.text().strip():
            return
        self.accept()

    def name(self) -> str:
        return self.name_edit.text().strip()

    def git_url(self) -> str:
        return self.git_url_edit.text().strip()

    def chosen_thumbnail_path(self) -> Path | None:
        return self._chosen_thumbnail_path

    def selected_program_ids(self) -> list[str]:
        return self.requirements_tree.selected_program_ids() if self.requirements_tree else []

    def selected_program_version_pins(self) -> dict[str, str]:
        return self.requirements_tree.selected_program_version_pins() if self.requirements_tree else {}
