from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from core.extensibility import notification_bus
from core.extensibility.config_store import PluginConfigStore
from core.extensibility.notification_bus import NotificationEntry
from core.store import LocalConfigStore
from plugins.core.Notification.notification_card import NotificationCard

SECTION_KEY = "notification"
_LAST_SEEN_KEY = "last_seen_at"


class NotificationPage(QWidget):
    """Notification's one section page — a scrollable list of NotificationCard
    for whatever notification_bus.entries_for(active_project_id,
    active_repo_id) currently returns (project-wide entries plus entries
    scoped to the active repo). Tracks "has the user opened this tab" via a
    per-machine PluginConfigStore (last_seen_at). badge_label is this page's
    own unread-count widget — plugin.py hands it to SectionSpec as a
    trailing_widget_factory (interface/section_registry.py), so
    SectionTabList only ever lays it out; this page updates its text/
    visibility directly, no SectionHost round-trip needed."""

    def __init__(self, *, local_config_store: LocalConfigStore, config_store: PluginConfigStore, parent=None):
        super().__init__(parent)
        self._local_config = local_config_store
        self._config_store = config_store

        self.badge_label = QLabel()
        self.badge_label.setObjectName("sectionTabBadge")
        self.badge_label.setVisible(False)

        self._cards_container = QWidget()
        self._cards_layout = QVBoxLayout(self._cards_container)
        self._cards_layout.setContentsMargins(10, 10, 10, 10)
        self._cards_layout.setSpacing(6)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setWidget(self._cards_container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll_area)

        self._refresh()

    # -- wiring (see plugin.py's _wire) --------------------------------------

    def on_bus_event(self, _entry: NotificationEntry) -> None:
        self._refresh()

    # -- section-page convention (MainWindow calls this on every repo switch)

    def set_repo(self, project, repo, workspace_root) -> None:
        self._refresh()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._mark_seen()

    # -- internals ------------------------------------------------------

    def _visible_entries(self) -> list[NotificationEntry]:
        project_id = self._local_config.active_project_id
        if not project_id:
            return []
        return notification_bus.entries_for(project_id, self._local_config.active_repo_id)

    def _refresh(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        entries = self._visible_entries()
        if not entries:
            empty_label = QLabel("No notifications yet.")
            empty_label.setProperty("secondary", True)
            self._cards_layout.addWidget(empty_label)
        else:
            for entry in entries:
                self._cards_layout.addWidget(NotificationCard(entry))
        self._cards_layout.addStretch(1)
        self._recompute_badge()

    def _mark_seen(self) -> None:
        self._config_store.set(_LAST_SEEN_KEY, datetime.now().isoformat())
        self._recompute_badge()

    def _recompute_badge(self) -> None:
        last_seen = self._config_store.get(_LAST_SEEN_KEY)
        unseen = [e for e in self._visible_entries() if last_seen is None or e.timestamp.isoformat() > last_seen]
        count = len(unseen)
        if count:
            self.badge_label.setText(str(count) if count <= 99 else "99+")
            self.badge_label.setVisible(True)
        else:
            self.badge_label.setVisible(False)
