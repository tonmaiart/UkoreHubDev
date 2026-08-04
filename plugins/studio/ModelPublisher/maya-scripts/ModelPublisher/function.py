"""Model publish logic — split out of the original UkorePublisher's
function.py (the "Model" branch of publish_dialog/publish_common) on
2026-07-19. Path resolution/versioning goes through PublishApi
(tickets.get_publish_root_for_ticket(TOOL_ID, ticket) +
versioning.get_version_directory()) instead of the old share/publish
scene-path convention — see plugins/studio/PublishApi/README.md. As of
2026-08-03, `ticket` is a user-managed dict (PublishApi.tickets, created/
edited via ticket_manager_dialog.py's "Manage Tickets..." button in this
tool's own Maya window) instead of a hardcoded string — its own
`folder_name` is the versioned subfolder, its own `publish_target`
resolves the root, and its own validation scripts (if any) must all pass
before this function is allowed to export anything. The old UkoreHub-side
Repo Studio Setting tab this used to defer the path choice to is gone."""

import os

import maya.cmds as mc
from PublishApi import tickets, versioning
from UkoreMaya.core import Pipeline

TOOL_ID = "model_publisher"


def publish(ticket: dict):
    """Exports the current scene as FBX + a raw Maya Ascii copy into this
    ticket's own resolved publish root, versioned automatically (mirrors
    the original UkorePublisher's Model branch: fbx + ma, just with
    user-managed tickets instead of a hardcoded list). Raises RuntimeError
    — meant to be shown directly to the artist — if the scene hasn't been
    saved, one of the ticket's validation scripts blocks the publish, or
    the ticket's own Publish Path can't be resolved. Returns (version_dir,
    version_number)."""
    scene_path = mc.file(q=True, sn=True)
    if not scene_path:
        raise RuntimeError("กรุณาบันทึกไฟล์ก่อนดำเนินการ Publish!")

    ok, message = tickets.run_validation_scripts(TOOL_ID, ticket)
    if not ok:
        raise RuntimeError(message)

    publish_root = tickets.get_publish_root_for_ticket(TOOL_ID, ticket)
    version_dir, version = versioning.get_version_directory(publish_root, ticket["folder_name"])

    fbx_path = os.path.join(version_dir, "{}_v{:03d}.fbx".format(ticket["folder_name"], version))
    Pipeline.export_fbx_common(export_path=fbx_path)

    ma_path = os.path.join(version_dir, "{}_v{:03d}.ma".format(ticket["folder_name"], version))
    Pipeline.export_maya_common(export_file_path=ma_path)

    return version_dir, version
