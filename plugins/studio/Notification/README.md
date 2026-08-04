# plugins/studio/Notification/

The first sidebar tab (`SectionSpec(order=1)`) — pure infrastructure. This
plugin never creates a notification itself; it only provides the shared card
template and an in-memory socket
(`core/extensibility/notification_bus.py`) that any other plugin
pushes into, plus the one page that renders them and tracks whether the
user has seen them.

## Using the socket from another plugin

```python
from core.extensibility import notification_bus

notification_bus.push(
    source="YourPlugin",
    project_id=project.id,
    repo_id=repo.id,       # or None — see "Scope" below
    label="Build finished for Character_Rig",
    icon_path=your_icon_path,       # optional, Path | None
    on_click=lambda: open_something(),  # optional, Callable[[], None]
)
```

No `api` handle needed — same direct-import, "construct/reach directly,
convention not import" pattern `core/extensibility/debug_log.py` already
uses (see `plugins/studio/DebugConsole/README.md` for that precedent).
Safe to call from deep runtime code (a background worker callback, a git
hook handler, etc.), not just inside `register(api)`.

## Scope: who decides "current Repo" vs. "All Repo in this project"

The **producer** decides at push time via `repo_id`:
- A specific `repo_id` → the notification only shows while that repo is
  active.
- `repo_id=None` → the notification shows regardless of which repo in that
  `project_id` is currently active.

The Notification page has no manual "This Repo / All Repos" toggle — it
auto-filters by whichever repo is active (`notification_bus.entries_for`),
consistent with the producer already having made that call.

## Not persisted

`notification_bus`'s entries live in memory only for the running session —
same reasoning as `debug_log.py`: a notification's `on_click` is a live
Python callback, which can't survive an app restart anyway. Only the
"has the user opened this tab" read-tracking (a single `last_seen_at`
timestamp) is persisted, in a per-machine `PluginConfigStore`
(`api.plugin_config_store("notification", shared=False)`) — never shared
between users, same as `software_linker`'s per-machine link paths.

## Files

- `manifest.json` — plugin id `notification`.
- `plugin.py` — `register(api)`: builds one `NotificationPage`, registers it
  as a section at `order=1` (lower than any other non-persistent section,
  so it's always first), wires it to `notification_bus.add_listener`, and
  hands `page.badge_label` to `SectionSpec.trailing_widget_factory`.
- `notification_card.py` — `NotificationCard(QFrame)`: the shared card
  template (icon, label, date/time, optional click action). Only clickable
  (pointer cursor + hover highlight) when the pushed entry has an
  `on_click`.
- `notification_page.py` — `NotificationPage`: the scrollable card list.
  Filters via `notification_bus.entries_for`, refreshes on every bus push
  and every repo switch (`set_repo`, the convention every section page
  implements), and marks the cache "seen" (clearing the badge) in
  `showEvent` — i.e. whenever the tab is actually switched to. Also owns
  `badge_label`, a plain `QLabel(objectName="sectionTabBadge")` it updates
  directly — see "Unread badge" below.

## Unread badge

`interface/section_registry.py`'s `SectionSpec.trailing_widget_factory` is a
general-purpose slot — a small widget shown at the right edge of a
section's own sidebar row, built once and laid out by
`interface/sidebar/section_tab_list.py`'s `SectionTabList`, which never
touches its content. It exists specifically so a future feature can put
*any* status widget there (not just a count), added while building this
plugin's unread badge but not Notification-specific.

Notification's own usage: `plugin.py` passes `lambda: page.badge_label`,
and `NotificationPage._recompute_badge` sets that label's text/visibility
directly (red background/white text via `core/theme.py`'s
`QLabel#sectionTabBadge` rule) whenever a notification arrives, the active
repo changes, or the tab is marked seen. No `SectionHost` round-trip —
the page just owns the widget.

Every sidebar row (fixed sections and dynamic Browser Link tabs alike) is
built as one composite widget via `SectionTabList._add_row`/`setItemWidget`,
not a native `QListWidgetItem` icon/text — this is what makes a row with a
trailing widget (Notification) look identical to one without (Explorer,
Submit, ...): every row goes through the exact same construction path, none
is a special case.
