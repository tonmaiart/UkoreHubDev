# plugins/core/RigPublisher/

Maya-side tool that publishes the active Rig scene (a raw Maya Ascii copy)
into a versioned folder. Split out of the original `UkorePublisher`
plugin's "Rig" branch on 2026-07-19, alongside
`ModelPublisher`/`AnimationPublisher` and the new `PublishApi` shared
library — see `plugins/core/PublishApi/README.md` and
`plugins/core/maya_launcher/README.md` for the bridge convention this
follows. Has its own dedicated UI now (no "Type" list — this plugin only
ever publishes Rig) instead of sharing one UI across every publish type
the way `UkorePublisher` used to.

## Files

- `manifest.json` — plugin id `rig_publisher`, entry point `plugin.py`.
- `plugin.py` — `register(api)`: contributes `maya-scripts/` to the shared
  `maya_launcher_env_bridge` `PluginConfigStore` (same convention every
  other Maya tool plugin here uses). Relies on `plugins/core/MayaToolkit`
  (for `UkoreMaya.core.Pipeline`'s export commands) and
  `plugins/core/PublishApi` (for path resolution/versioning/tickets)
  also being enabled — not imported directly, just expected on the same
  merged PYTHONPATH once Maya launches. **No longer registers a UkoreHub
  Settings tab** (removed 2026-08-03 — see "What changed" below).
- `maya-scripts/RigPublisher/function.py` — `TOOL_ID = "rig_publisher"`,
  `publish(ticket: dict)`: runs the ticket's validation scripts
  (`PublishApi.tickets.run_validation_scripts`, raising `RuntimeError` on
  failure), resolves the publish root via
  `PublishApi.tickets.get_publish_root_for_ticket(TOOL_ID, ticket)` (the
  ticket's own chosen pipeline connection, already scoped to its
  `CustomPath`), creates the next version folder via
  `PublishApi.versioning.get_version_directory()` using the ticket's own
  `folder_name`, then exports `<folder_name>_v<NNN>.ma`
  (`Pipeline.export_maya_common`) into it.
- `maya-scripts/RigPublisher/interface.py` — `MainWindow`
  (`tmlib.ui.interface_template.ToolkitWindow`): same shape as
  `plugins/core/ModelPublisher/`'s own `interface.py` — ticket list +
  snapshot/publish/open-folder buttons, plus a "Manage Tickets..." button
  (added 2026-08-03, inserted in code rather than in `ui.ui`) that opens
  `PublishApi.ticket_manager_dialog.TicketManagerDialog`. Tickets are
  loaded from `PublishApi.tickets.list_tickets(TOOL_ID)` — no more
  hardcoded list — and `get_current_selected_ticket()` returns the full
  ticket dict, not a bare string. `refresh_publish_destination()`
  re-resolves the root/version live as the ticket changes.
- `maya-scripts/RigPublisher/ui.ui` — Qt Designer layout, loaded via
  `importlib.import_module("RigPublisher")` + `__path__[0]/ui.ui`.

## What changed from the original UkorePublisher

Same as `plugins/core/ModelPublisher/README.md`'s "What changed" section
— publish root now always comes from `PublishApi`'s pipeline-connection
resolution instead of the old `share`/`publish` scene-path convention, no
more Type selection, and the free-text "Custom Path" field artists used to
type in Maya is gone.

**2026-08-03**: the "which pipeline connection to publish into" choice
moved from a single per-repo pick in a UkoreHub Settings tab
(`RigPublisherSettingsPage`, now deleted) to a **per-ticket** choice made
entirely in Maya via "Manage Tickets..." — see
`plugins/core/PublishApi/README.md`'s "Tickets" section for the full
shape (user-created tickets, separate name/folder, per-ticket Publish
Path, per-ticket validation scripts). An existing repo's old single choice
is auto-migrated into a "Main" ticket the first time its tickets are
listed, so nothing already configured is lost.

## Working on this plugin

Read/edit only files under this folder unless the change is specifically
about `PublishApi`'s API surface (a genuine cross-plugin task) — see the
`ukorehub-plugin` skill.
