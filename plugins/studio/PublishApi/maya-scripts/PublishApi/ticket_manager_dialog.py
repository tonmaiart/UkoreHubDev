"""Shared "Manage Tickets..." dialog for every PublishApi-based Publisher
tool (ModelPublisher, RigPublisher, AnimationPublisher) — lets a studio
admin create/rename/delete tickets, pick each ticket's own Publish Path
(one of the active repo's declared pipeline connections), and attach/
detach per-ticket validation scripts, entirely from inside Maya. Replaces
the old
UkoreHub-side Repo Studio Setting tab (RigPublisherSettingsPage etc.,
removed 2026-08-03) now that this configuration is per-ticket rather than
per-repo — see tickets.py for the storage/resolution logic this dialog is
just a UI over.

Opened from each Publisher's own interface.py via a "Manage Tickets..."
button, parameterized by tool_id/tool_label/show_export_type so this one
dialog class serves all three tools (same "one shared implementation, thin
per-tool usage" pattern PublishApi/publish_target_settings_page.py used on
the UkoreHub side before it was removed). "Save Publish Path" is an
explicit button, not autosave-on-click — same deliberate-commit convention
publish_target_settings_page.py adopted, for the same reason (a silent
autosave reads as "did my choice even save?" with no visible confirmation).

Validation scripts (added 2026-08-03) are picked from a **fixed** folder —
tickets.validation_scripts_dir(tool_id), physically inside the active
repo's own local clone — not authored here: a TD writes/commits the
actual .py files outside this dialog entirely (this dialog just has
"Open Script Folder..." to jump there). The script list is a checkable
list (checked = attached to the selected ticket), toggling a checkbox
attaches/detaches immediately (tickets.attach_script/detach_script) —
same self-persisting-checkbox convention Requirements/Enable Plugin use
elsewhere in this codebase, since toggling which existing script applies
is a much lower-stakes action than picking a Publish Path."""

from __future__ import annotations

import os

from tmlib.module.PySide import QtCore, QtWidgets

from PublishApi import repo_paths, tickets


class TicketManagerDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, tool_id: str, tool_label: str, show_export_type: bool = False):
        super().__init__(parent)
        self._tool_id = tool_id
        self._show_export_type = show_export_type
        self._tickets: list[dict] = []
        self._connections: list[dict] = []

        self.setWindowTitle(f"{tool_label} — Manage Tickets")
        self.resize(640, 420)

        # -- Left: ticket list + New/Rename/Delete --------------------
        self.ticket_list = QtWidgets.QListWidget()
        self.ticket_list.currentRowChanged.connect(self._on_ticket_selected)

        self.new_button = QtWidgets.QPushButton("New...")
        self.rename_button = QtWidgets.QPushButton("Rename...")
        self.delete_button = QtWidgets.QPushButton("Delete")
        self.new_button.clicked.connect(self._on_new_ticket)
        self.rename_button.clicked.connect(self._on_rename_ticket)
        self.delete_button.clicked.connect(self._on_delete_ticket)

        left_buttons = QtWidgets.QHBoxLayout()
        left_buttons.addWidget(self.new_button)
        left_buttons.addWidget(self.rename_button)
        left_buttons.addWidget(self.delete_button)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(QtWidgets.QLabel("Tickets"))
        left_layout.addWidget(self.ticket_list)
        left_layout.addLayout(left_buttons)

        # -- Right: Publish Path + Export Type + Validation Scripts ---
        self.publish_path_list = QtWidgets.QListWidget()
        self.publish_path_save_button = QtWidgets.QPushButton("Save Publish Path")
        self.publish_path_save_button.setEnabled(False)
        self.publish_path_list.itemSelectionChanged.connect(self._on_publish_path_selection_changed)
        self.publish_path_save_button.clicked.connect(self._on_save_publish_path)

        self.export_type_combo = QtWidgets.QComboBox()
        self.export_type_combo.addItems(["Playblast", "Unreal Export"])
        self.export_type_combo.currentIndexChanged.connect(self._on_export_type_changed)
        self.export_type_combo.setVisible(show_export_type)

        self.script_list = QtWidgets.QListWidget()
        self.script_list.itemChanged.connect(self._on_script_check_changed)
        self.refresh_scripts_button = QtWidgets.QPushButton("Refresh Scripts")
        self.open_script_folder_button = QtWidgets.QPushButton("Open Script Folder...")
        self.refresh_scripts_button.clicked.connect(self._on_refresh_scripts)
        self.open_script_folder_button.clicked.connect(self._on_open_script_folder)

        script_buttons = QtWidgets.QHBoxLayout()
        script_buttons.addWidget(self.refresh_scripts_button)
        script_buttons.addWidget(self.open_script_folder_button)

        right_layout = QtWidgets.QVBoxLayout()
        right_layout.addWidget(QtWidgets.QLabel("Publish Path"))
        right_layout.addWidget(self.publish_path_list)
        right_layout.addWidget(self.publish_path_save_button)
        if show_export_type:
            right_layout.addWidget(QtWidgets.QLabel("Export Type"))
            right_layout.addWidget(self.export_type_combo)
        right_layout.addWidget(QtWidgets.QLabel("Validation Scripts"))
        right_layout.addWidget(self.script_list)
        right_layout.addLayout(script_buttons)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=1)

        self.refresh()

    # ------------------------------------------------------------
    # Ticket list
    # ------------------------------------------------------------
    def refresh(self) -> None:
        """Reloads tickets from disk and re-renders both panes. Keeps
        whichever ticket was selected before (by id, not row index) —
        always explicitly re-runs _refresh_ticket_detail regardless of
        whether the restored row differs from before, since
        currentRowChanged only fires on an actual row change and a
        just-saved edit to the *same* selected ticket wouldn't otherwise
        show up."""
        current_id = self._current_ticket_id()
        self._tickets = tickets.list_tickets(self._tool_id)

        self.ticket_list.blockSignals(True)
        self.ticket_list.clear()
        for ticket in self._tickets:
            self.ticket_list.addItem(ticket["name"])

        restore_row = 0
        for index, ticket in enumerate(self._tickets):
            if ticket["id"] == current_id:
                restore_row = index
                break
        if self._tickets:
            self.ticket_list.setCurrentRow(restore_row)
        self.ticket_list.blockSignals(False)

        self._refresh_ticket_detail(self._tickets[restore_row] if self._tickets else None)

    def _current_ticket_id(self) -> str | None:
        row = self.ticket_list.currentRow()
        if 0 <= row < len(self._tickets):
            return self._tickets[row]["id"]
        return None

    def _current_ticket(self) -> dict | None:
        row = self.ticket_list.currentRow()
        if 0 <= row < len(self._tickets):
            return self._tickets[row]
        return None

    def _on_ticket_selected(self, row: int) -> None:
        ticket = self._tickets[row] if 0 <= row < len(self._tickets) else None
        self._refresh_ticket_detail(ticket)

    def _on_new_ticket(self) -> None:
        name, ok = QtWidgets.QInputDialog.getText(self, "New Ticket", "Ticket name:")
        if not ok or not name.strip():
            return
        name = name.strip()
        folder_name, ok = QtWidgets.QInputDialog.getText(
            self, "New Ticket", "Folder name (cannot be changed later):", text=name
        )
        if not ok or not folder_name.strip():
            return
        try:
            tickets.create_ticket(self._tool_id, name, folder_name.strip())
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, "Cannot Create Ticket", str(exc))
            return
        self.refresh()

    def _on_rename_ticket(self) -> None:
        ticket = self._current_ticket()
        if ticket is None:
            return
        new_name, ok = QtWidgets.QInputDialog.getText(self, "Rename Ticket", "Ticket name:", text=ticket["name"])
        if not ok or not new_name.strip():
            return
        tickets.rename_ticket(self._tool_id, ticket["id"], new_name.strip())
        self.refresh()

    def _on_delete_ticket(self) -> None:
        ticket = self._current_ticket()
        if ticket is None:
            return
        result = QtWidgets.QMessageBox.question(
            self,
            "Delete Ticket",
            f"Delete ticket '{ticket['name']}'? Its already-published files and validation "
            "scripts are not deleted, only the ticket entry itself.",
        )
        if result != QtWidgets.QMessageBox.Yes:
            return
        tickets.delete_ticket(self._tool_id, ticket["id"])
        self.refresh()

    # ------------------------------------------------------------
    # Per-ticket detail (Publish Path / Export Type / Scripts)
    # ------------------------------------------------------------
    def _refresh_ticket_detail(self, ticket: dict | None) -> None:
        self.publish_path_list.clear()
        self.script_list.clear()
        self._connections = []
        has_ticket = ticket is not None

        self.publish_path_list.setEnabled(has_ticket)
        self.script_list.setEnabled(has_ticket)
        self.refresh_scripts_button.setEnabled(has_ticket)
        self.open_script_folder_button.setEnabled(has_ticket)
        self.export_type_combo.setEnabled(has_ticket)
        self.publish_path_save_button.setEnabled(False)

        if ticket is None:
            return

        self._connections = repo_paths.get_pipeline_refs()
        chosen = ticket.get("publish_target")
        for index, ref in enumerate(self._connections):
            self.publish_path_list.addItem(self._describe_ref(ref))
            if chosen is not None and self._same_ref(ref, chosen):
                self.publish_path_list.setCurrentRow(index)

        if self._show_export_type:
            export_type = ticket.get("export_type", "playblast")
            self.export_type_combo.blockSignals(True)
            self.export_type_combo.setCurrentIndex(1 if export_type == "unreal" else 0)
            self.export_type_combo.blockSignals(False)

        self._populate_script_list(ticket)

    def _populate_script_list(self, ticket: dict) -> None:
        """Checkable list of every .py file in this repo's fixed
        validation-script folder for this tool — checked if attached to
        `ticket`. Signals blocked while building so this doesn't fire
        _on_script_check_changed for every row."""
        attached = set(ticket.get("script_names", []))
        self.script_list.blockSignals(True)
        self.script_list.clear()
        try:
            available = tickets.list_available_scripts(self._tool_id)
        except RuntimeError:
            available = []
        for script_path in available:
            item = QtWidgets.QListWidgetItem(script_path.name)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.Checked if script_path.name in attached else QtCore.Qt.Unchecked)
            self.script_list.addItem(item)
        self.script_list.blockSignals(False)

    @staticmethod
    def _same_ref(a: dict, b: dict) -> bool:
        return (
            a.get("project_id") == b.get("project_id")
            and a.get("repo_id") == b.get("repo_id")
            and a.get("custom_path_id") == b.get("custom_path_id")
        )

    def _describe_ref(self, ref: dict) -> str:
        from core.exceptions import NotFoundError
        from core.store import MetadataStore

        root = repo_paths.find_ukorehub_root()
        store = MetadataStore(root / "data" / "projects.json")
        try:
            target_name = store.get_repo(ref["project_id"], ref["repo_id"]).name
        except NotFoundError:
            target_name = "(deleted repo)"
        custom_path = repo_paths.get_custom_path(ref["project_id"], ref["repo_id"], ref.get("custom_path_id"))
        label = custom_path["label"] if custom_path else "(deleted custom path)"
        return f"{target_name} — {label}"

    def _on_publish_path_selection_changed(self) -> None:
        self.publish_path_save_button.setEnabled(self.publish_path_list.currentRow() >= 0)

    def _on_save_publish_path(self) -> None:
        ticket = self._current_ticket()
        row = self.publish_path_list.currentRow()
        if ticket is None or not (0 <= row < len(self._connections)):
            return
        tickets.set_ticket_publish_target(self._tool_id, ticket["id"], self._connections[row])
        self.refresh()

    def _on_export_type_changed(self, index: int) -> None:
        ticket = self._current_ticket()
        if ticket is None:
            return
        tickets.set_ticket_export_type(self._tool_id, ticket["id"], "unreal" if index == 1 else "playblast")

    # ------------------------------------------------------------
    # Validation scripts — attach/detach existing files only, never
    # authored here (see class docstring)
    # ------------------------------------------------------------
    def _on_script_check_changed(self, item) -> None:
        ticket = self._current_ticket()
        if ticket is None:
            return
        script_name = item.text()
        if item.checkState() == QtCore.Qt.Checked:
            tickets.attach_script(self._tool_id, ticket["id"], script_name)
        else:
            tickets.detach_script(self._tool_id, ticket["id"], script_name)

    def _on_refresh_scripts(self) -> None:
        ticket = self._current_ticket()
        if ticket is None:
            return
        self._populate_script_list(ticket)

    def _on_open_script_folder(self) -> None:
        ticket = self._current_ticket()
        if ticket is None:
            return
        try:
            folder = tickets.validation_scripts_dir(self._tool_id)
        except RuntimeError as exc:
            QtWidgets.QMessageBox.warning(self, "Cannot Open Folder", str(exc))
            return
        os.startfile(str(folder))
