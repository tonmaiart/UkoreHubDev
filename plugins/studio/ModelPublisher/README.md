# plugins/studio/ModelPublisher/

Maya-side tool that publishes the active Model scene (FBX + a raw Maya
Ascii copy) into a versioned folder. Split out of the original
`UkorePublisher` plugin's "Model" branch on 2026-07-19, alongside
`RigPublisher`/`AnimationPublisher` and the new `PublishApi` shared
library — see `plugins/studio/PublishApi/README.md` and
`plugins/studio/maya_launcher/README.md` for the bridge convention this
follows. Has its own dedicated UI now (no "Type" list — this plugin only
ever publishes Model) instead of sharing one UI across every publish type
the way `UkorePublisher` used to.

## Files

- `manifest.json` — plugin id `model_publisher`, entry point `plugin.py`.
- `plugin.py` — `register(api)`: contributes `maya-scripts/` to the shared
  `maya_launcher_env_bridge` `PluginConfigStore` (same convention every
  other Maya tool plugin here uses). Relies on `plugins/studio/MayaToolkit`
  (for `UkoreMaya.core.Pipeline`'s export commands) and
  `plugins/studio/PublishApi` (for path resolution/versioning/tickets)
  also being enabled — not imported directly, just expected on the same
  merged PYTHONPATH once Maya launches. **No longer registers a UkoreHub
  Settings tab** (removed 2026-08-03 — see "What changed" below).
- `maya-scripts/ModelPublisher/function.py` — `TOOL_ID = "model_publisher"`,
  `publish(ticket: dict)`: runs the ticket's validation scripts
  (`PublishApi.tickets.run_validation_scripts`, raising `RuntimeError` on
  failure), resolves the publish root via
  `PublishApi.tickets.get_publish_root_for_ticket(TOOL_ID, ticket)` (the
  ticket's own chosen pipeline connection, already scoped to its
  `CustomPath`), creates the next version folder via
  `PublishApi.versioning.get_version_directory()` using the ticket's own
  `folder_name`, then exports `<folder_name>_v<NNN>.fbx`
  (`Pipeline.export_fbx_common`) and `<folder_name>_v<NNN>.ma`
  (`Pipeline.export_maya_common`) into it.
- `maya-scripts/ModelPublisher/interface.py` — `MainWindow`
  (`tmlib.ui.interface_template.ToolkitWindow`): ticket list, snapshot
  button, publish/open-folder buttons, plus a "Manage Tickets..." button
  (added 2026-08-03, inserted in code rather than in `ui.ui`) that opens
  `PublishApi.ticket_manager_dialog.TicketManagerDialog`. Tickets are
  loaded from `PublishApi.tickets.list_tickets(TOOL_ID)` — no more
  hardcoded list — and `get_current_selected_ticket()` returns the full
  ticket dict, not a bare string. `refresh_publish_destination()`
  re-resolves the root and next version live as the ticket changes,
  showing a clear error message from `PublishApi.tickets` (no active repo
  / this ticket has no Publish Path set / target repo not cloned) instead
  of a blank or stale destination.
- `maya-scripts/ModelPublisher/ui.ui` — Qt Designer layout, loaded by
  `tmlib.ui.interface_template.ToolkitWindow` via
  `importlib.import_module("ModelPublisher")` + `__path__[0]/ui.ui` (same
  convention `plugins/studio/UkoreBrowser/`'s own `ui.ui` uses).

## What changed from the original UkorePublisher

- Publish root: used to come from string-swapping `.../share/...` for
  `.../publish/...` in the current scene's own file path
  (`UkoreMaya/core/Logic.py`'s `convert_to_publish_path`). Now it's always
  `PublishApi.tickets.get_publish_root_for_ticket("model_publisher", ticket)`
  — a specific ticket's own declared pipeline connection in Project
  Editor, scoped to a specific `CustomPath`.
- "Type" selection is gone — this plugin only ever publishes Model, so
  there's no type list, just the ticket list.
- The free-text "Custom Path" field artists used to type in Maya (added
  2026-07-19, removed the same day) is gone — replaced first by a
  UkoreHub-side picker, then (2026-08-03) by per-ticket Publish Paths
  configured entirely in Maya, since the whole point of `CustomPath` is to
  be a small, curated, studio-declared catalog
  (`plugins/studio/project_editor`'s "Custom Paths" tab), not something an
  artist free-types per publish.

**2026-08-03**: the "which pipeline connection to publish into" choice
moved from a single per-repo pick in a UkoreHub Settings tab
(`ModelPublisherSettingsPage`, now deleted) to a **per-ticket** choice made
entirely in Maya via "Manage Tickets..." — see
`plugins/studio/PublishApi/README.md`'s "Tickets" section for the full
shape (user-created tickets, separate name/folder, per-ticket Publish
Path, per-ticket validation scripts). An existing repo's old single choice
is auto-migrated into a "Main" ticket the first time its tickets are
listed, so nothing already configured is lost.

## Working on this plugin

Read/edit only files under this folder unless the change is specifically
about `PublishApi`'s API surface (a genuine cross-plugin task) — see the
`ukorehub-plugin` skill.
