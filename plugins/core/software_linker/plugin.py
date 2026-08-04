from __future__ import annotations

import os
import shutil
import winreg

from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFileIconProvider,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from interface.settings_tab_registry import SettingsTabSpec

PLUGIN_ID = "software_linker"

# The same registry locations Windows' own "Programs and Features" /
# Settings > Apps reads from.
_UNINSTALL_ROOTS = [
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
]


def _resolve_exe_path(sub_key) -> str | None:
    try:
        icon_value = winreg.QueryValueEx(sub_key, "DisplayIcon")[0]
        exe_path = icon_value.split(",")[0].strip('"')
        if exe_path.lower().endswith(".exe") and os.path.isfile(exe_path):
            return exe_path
    except OSError:
        pass
    try:
        install_location = winreg.QueryValueEx(sub_key, "InstallLocation")[0]
        if install_location and os.path.isdir(install_location):
            for name in os.listdir(install_location):
                if name.lower().endswith(".exe"):
                    return os.path.join(install_location, name)
    except OSError:
        pass
    return None


def list_installed_programs() -> list[tuple[str, str]]:
    """Best-effort scan of every program registered in Windows' Uninstall
    registry keys — the same list "Programs and Features"/Settings > Apps
    shows. Returns (display_name, resolved_exe_path) pairs, skipping any
    entry we can't resolve to an actual .exe (some only have an uninstaller
    or a generic icon, no runnable target)."""
    programs: dict[str, str] = {}
    for hive, subkey_path in _UNINSTALL_ROOTS:
        try:
            root_key = winreg.OpenKey(hive, subkey_path)
        except OSError:
            continue
        with root_key:
            count = winreg.QueryInfoKey(root_key)[0]
            for i in range(count):
                try:
                    sub_name = winreg.EnumKey(root_key, i)
                    with winreg.OpenKey(root_key, sub_name) as sub_key:
                        display_name = winreg.QueryValueEx(sub_key, "DisplayName")[0]
                        exe_path = _resolve_exe_path(sub_key)
                except OSError:
                    continue
                if exe_path:
                    programs[display_name] = exe_path
    return sorted(programs.items())


class ProgramPickerDialog(QDialog):
    """Simple icon+search picker over every installed program found in the
    Windows registry — not a file-path browse (see "Browse Path..." for
    that), this is specifically "pick from what's already installed"."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose Installed Program")
        self.resize(480, 520)
        self._selected_path: str | None = None

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search installed programs...")
        self.search_edit.textChanged.connect(self._apply_filter)

        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(32, 32))
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)

        icon_provider = QFileIconProvider()
        for name, path in list_installed_programs():
            item = QListWidgetItem(icon_provider.icon(QFileInfo(path)), name)
            item.setData(Qt.UserRole, path)
            item.setToolTip(path)
            self.list_widget.addItem(item)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_edit)
        layout.addWidget(self.list_widget)
        layout.addWidget(buttons)

    def _apply_filter(self, text: str) -> None:
        text = text.lower()
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            item.setHidden(bool(text) and text not in item.text().lower())

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        self._selected_path = item.data(Qt.UserRole)
        self.accept()

    def _on_accept(self) -> None:
        items = self.list_widget.selectedItems()
        if not items:
            return
        self._selected_path = items[0].data(Qt.UserRole)
        self.accept()

    def selected_path(self) -> str | None:
        return self._selected_path


def _linked_key(program, version: str = "") -> str:
    """Per-machine linked-exe config key. Stays plain program.id for a
    single/no-version Program (preserves already-linked paths); becomes
    "<id>:<version>" once a Program has multiple versions, since each
    needs its own linked executable. Convention-only duplicate of
    plugins/core/maya_launcher/link_resolution.py's linked_key() — keep
    both in sync if this shape ever changes, same discipline as
    MAYA_ENV_BRIDGE_PLUGIN_ID."""
    if len(program.versions) <= 1:
        return program.id
    return f"{program.id}:{version}"


def _link_rows(program_store):
    """(key, program, version, label) for every linkable (Program, version)
    slot — one row for a single/no-version Program, one row per version
    for a multi-version Program (e.g. Maya 2024 and 2026 need separate
    linked executables)."""
    rows = []
    for program in program_store.list_programs():
        versions = program.versions or [""]
        if len(versions) <= 1:
            version = versions[0]
            label = f"{program.name} (v{version})" if version else program.name
            rows.append((_linked_key(program, version), program, version, label))
        else:
            for version in versions:
                rows.append((_linked_key(program, version), program, version, f"{program.name} (v{version})"))
    return rows


class SoftwareLinkerPage(QWidget):
    """Lets the user link each Program Database entry to a local executable
    path on this machine — per-machine data (PluginConfigStore, shared=False),
    since "what's installed here" is never team-shared. Other plugins/add-ons
    (e.g. MayaLauncher) read the same mapping by calling
    api.plugin_config_store("software_linker", shared=False) themselves —
    no coupling API needed, just agreeing on that id string."""

    def __init__(self, parent=None, *, program_store, config_store):
        super().__init__(parent)
        self._program_store = program_store
        self._config_store = config_store

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SingleSelection)

        browse_program_btn = QPushButton("Browse Program...")
        browse_program_btn.clicked.connect(self._on_browse_program)
        browse_path_btn = QPushButton("Browse Path...")
        browse_path_btn.clicked.connect(self._on_browse_path)
        clear_btn = QPushButton("Clear Link")
        clear_btn.clicked.connect(self._on_clear)

        button_row = QHBoxLayout()
        button_row.addWidget(browse_program_btn)
        button_row.addWidget(browse_path_btn)
        button_row.addWidget(clear_btn)
        button_row.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(self.list_widget)
        layout.addLayout(button_row)

        self._auto_detect_missing()
        self._refresh_list()

    def _auto_detect_missing(self) -> None:
        # Best-effort only — checks the system PATH for an executable that
        # looks like the program's name, nothing more. Programs with no
        # match just stay unlinked until the user links one manually.
        for key, program, _version, _label in _link_rows(self._program_store):
            if self._config_store.get(key):
                continue
            guess = shutil.which(program.name.lower().replace(" ", ""))
            if guess:
                self._config_store.set(key, guess)

    def _refresh_list(self) -> None:
        self.list_widget.clear()
        for key, _program, _version, label in _link_rows(self._program_store):
            linked_path = self._config_store.get(key)
            status = linked_path if linked_path else "Not linked"
            item = QListWidgetItem(f"{label} — {status}")
            item.setData(Qt.UserRole, key)
            self.list_widget.addItem(item)

    def _selected_link_key(self) -> str | None:
        items = self.list_widget.selectedItems()
        if not items:
            return None
        return items[0].data(Qt.UserRole)

    def _on_browse_program(self) -> None:
        key = self._selected_link_key()
        if not key:
            return
        dialog = ProgramPickerDialog(self)
        if dialog.exec() and dialog.selected_path():
            self._config_store.set(key, dialog.selected_path())
            self._refresh_list()

    def _on_browse_path(self) -> None:
        key = self._selected_link_key()
        if not key:
            return
        file_path, _filter = QFileDialog.getOpenFileName(self, "Select Executable")
        if not file_path:
            return
        self._config_store.set(key, file_path)
        self._refresh_list()

    def _on_clear(self) -> None:
        key = self._selected_link_key()
        if not key:
            return
        self._config_store.set(key, None)
        self._refresh_list()


def register(api) -> None:
    api.register_settings_tab(
        SettingsTabSpec(
            key=PLUGIN_ID,
            label="Software Linker",
            order=100,
            page_factory=lambda: SoftwareLinkerPage(
                program_store=api.programs,
                config_store=api.plugin_config_store(PLUGIN_ID, shared=False),
            ),
        )
    )
