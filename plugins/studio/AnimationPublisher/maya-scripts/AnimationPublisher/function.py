"""Animation publish logic — split out of the original UkorePublisher's
function.py (the "Anim" branch of publish_dialog/publish_common) on
2026-07-19. Path resolution/versioning goes through PublishApi
(tickets.get_publish_root_for_ticket(TOOL_ID, ticket) +
versioning.get_version_directory()) instead of the old share/publish
scene-path convention — see plugins/studio/PublishApi/README.md. As of
2026-08-03, `ticket` is a user-managed dict (PublishApi.tickets, created/
edited via ticket_manager_dialog.py's "Manage Tickets..." button in this
tool's own Maya window) instead of a hardcoded string.

The old Main/Layout/Blocking/Polish/Playblast fixed ticket names are gone
— tickets are free-form now, so which export a ticket does is its own
explicit `export_type` field ("playblast" or "unreal") instead of being
inferred from the ticket's name. "unreal" still raises the same
not-yet-implemented error as before: the original tool's Unreal-export
branch called UkoreMaya.core.Pipeline.export_shot_to_ue(...), a function
that doesn't exist anywhere in Pipeline.py. That gap predates this split
(it was already broken in the original UkorePublisher) and isn't
something this refactor invents an implementation for."""

import os

import maya.cmds as mc
from PublishApi import tickets, versioning
from UkoreMaya.core import Pipeline

TOOL_ID = "animation_publisher"


def publish(ticket: dict):
    """Exports a playblast (.avi) into this ticket's own resolved publish
    root, versioned automatically, when ticket["export_type"] == "playblast".
    Raises RuntimeError for "unreal" (see module docstring), if the scene
    hasn't been saved, if one of the ticket's validation scripts blocks the
    publish, or if the ticket's own Publish Path can't be resolved. Returns
    (version_dir, version_number)."""
    scene_path = mc.file(q=True, sn=True)
    if not scene_path:
        raise RuntimeError("กรุณาบันทึกไฟล์ก่อนดำเนินการ Publish!")

    export_type = ticket.get("export_type", "playblast")
    if export_type != "playblast":
        raise RuntimeError(
            "'{}' is set to Unreal Export, which isn't implemented yet — "
            "Pipeline.export_shot_to_ue doesn't exist in plugins/studio/MayaToolkit's "
            "UkoreMaya.core.Pipeline (a pre-existing gap from the original UkorePublisher "
            "tool, not something this split fixed). Switch this ticket to Playblast under "
            "Manage Tickets... to publish it.".format(ticket["name"])
        )

    ok, message = tickets.run_validation_scripts(TOOL_ID, ticket)
    if not ok:
        raise RuntimeError(message)

    publish_root = tickets.get_publish_root_for_ticket(TOOL_ID, ticket)
    version_dir, version = versioning.get_version_directory(publish_root, ticket["folder_name"])

    avi_path = os.path.join(version_dir, "{}_v{:03d}.avi".format(ticket["folder_name"], version))
    Pipeline.export_playblast(export_path=avi_path)

    return version_dir, version
