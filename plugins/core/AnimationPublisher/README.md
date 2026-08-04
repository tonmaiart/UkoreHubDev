# plugins/studio/AnimationPublisher/

Maya-side tool that publishes the active Animation scene (a playblast
`.avi` for tickets set to Playblast) into a versioned folder. Split out
of the original `UkorePublisher` plugin's "Anim" branch on 2026-07-19,
alongside `ModelPublisher`/`RigPublisher` and the new `PublishApi` shared
library — see `plugins/studio/PublishApi/README.md` and
`plugins/studio/maya_launcher/README.md` for the bridge convention this
follows. Has its own dedicated UI now (no "Type" list — this plugin only
ever publishes Animation) instead of sharing one UI across every publish
type the way `UkorePublisher` used to.

## Files

- `manifest.json` — plugin id `animation_publisher`, entry point
  `plugin.py`.
- `plugin.py` — `register(api)`: contributes `maya-scripts/` to the shared
  `maya_launcher_env_bridge` `PluginConfigStore` (same convention every
  other Maya tool plugin here uses). Relies on `plugins/studio/MayaToolkit`
  (for `UkoreMaya.core.Pipeline`'s export commands) and
  `plugins/studio/PublishApi` (for path resolution/versioning/tickets)
  also being enabled — not imported directly, just expected on the same
  merged PYTHONPATH once Maya launches. **No longer registers a UkoreHub
  Settings tab** (removed 2026-08-03 — see "What changed" below).
- `maya-scripts/AnimationPublisher/function.py` — `TOOL_ID =
  "animation_publisher"`, `publish(ticket: dict)`: as of 2026-08-03,
  tickets are user-created (no more fixed name list) — which export a
  ticket does is its own explicit `ticket["export_type"]` field
  (`"playblast"` or `"unreal"`, set per ticket via "Manage Tickets...",
  see `interface.py` below) instead of being inferred from a hardcoded
  ticket name. For `"playblast"`: runs the ticket's validation scripts
  (`PublishApi.tickets.run_validation_scripts`, raising `RuntimeError` on
  failure), resolves the publish root via
  `PublishApi.tickets.get_publish_root_for_ticket(TOOL_ID, ticket)`,
  creates the next version folder via
  `PublishApi.versioning.get_version_directory()` using the ticket's own
  `folder_name`, then exports `<folder_name>_v<NNN>.avi`
  (`Pipeline.export_playblast`).

  **`"unreal"` raises a clear `RuntimeError` instead of publishing
  anything.** The original `UkorePublisher`'s equivalent branch called
  `UkoreMaya.core.Pipeline.export_shot_to_ue(...)`, a function that
  doesn't exist anywhere in `plugins/studio/MayaToolkit`'s
  `UkoreMaya/core/Pipeline.py` — this was already broken before the
  2026-07-19 split, not something this refactor introduced or "fixed" by
  guessing at what that export should actually do. Implement
  `Pipeline.export_shot_to_ue` (or whatever the real intended export is)
  first, then wire `export_type == "unreal"` up to it here.
- `maya-scripts/AnimationPublisher/interface.py` — `MainWindow`
  (`tmlib.ui.interface_template.ToolkitWindow`): same shape as
  `plugins/studio/ModelPublisher/`'s own `interface.py` — ticket list +
  snapshot/publish/open-folder buttons, plus a "Manage Tickets..." button
  (added 2026-08-03, inserted in code rather than in `ui.ui`) that opens
  `PublishApi.ticket_manager_dialog.TicketManagerDialog` with
  `show_export_type=True` — the only one of the three Publishers that
  passes this, since Rig/Model tickets have no export-type choice.
  Publishing a ticket set to Unreal Export shows `function.publish`'s
  `RuntimeError` message in a `confirmDialog` rather than silently
  failing.
- `maya-scripts/AnimationPublisher/ui.ui` — Qt Designer layout, loaded via
  `importlib.import_module("AnimationPublisher")` + `__path__[0]/ui.ui`.

## What changed from the original UkorePublisher

Same as `plugins/studio/ModelPublisher/README.md`'s "What changed" section
— publish root now always comes from `PublishApi`'s pipeline-connection
resolution instead of the old `share`/`publish` scene-path convention, no
more Type selection, and the free-text "Custom Path" field artists used to
type in Maya is gone. The Unreal Export gap above is unrelated to that
change — it was carried forward as-is from the original tool, just made
explicit instead of silently crashing on a missing attribute.

**2026-08-03**: the fixed `TICKETS = ["Main", "Layout", "Blocking",
"Polish", "Playblast"]` list (with Main/Playblast doing a real playblast
export and the other three always raising the Unreal-export error) is
gone — tickets are user-created now, and the old "which fixed name" gate
became an explicit per-ticket `export_type` field (Playblast / Unreal
Export) set via "Manage Tickets...", preserving the same behavior (Unreal
Export still isn't implemented) without depending on a specific ticket
name. The "which pipeline connection to publish into" choice also moved
the same day, from a single per-repo pick in a UkoreHub Settings tab
(`AnimationPublisherSettingsPage`, now deleted) to a **per-ticket** choice
— see `plugins/studio/PublishApi/README.md`'s "Tickets" section for the
full shape. An existing repo's old single Publish Path choice is
auto-migrated into a "Main" ticket (defaulting to `export_type:
"playblast"`) the first time its tickets are listed, so nothing already
configured is lost.

## Working on this plugin

Read/edit only files under this folder unless the change is specifically
about `PublishApi`'s API surface (a genuine cross-plugin task) — see the
`ukorehub-plugin` skill.
