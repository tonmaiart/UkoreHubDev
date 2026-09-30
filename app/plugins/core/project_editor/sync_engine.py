from __future__ import annotations

STATUS_CONFLICT = "conflict"
STATUS_BROKEN_GIT = "broken_git"
STATUS_ERROR = "error"

# Statuses worth remembering in ExternalPluginSyncStatusStore — see
# sync_status_store.py. Auto-sync itself moved to Portal
# (portal/plugin_update.py), which never writes this store.
PERSISTENT_STATUSES = {STATUS_CONFLICT, STATUS_ERROR, STATUS_BROKEN_GIT}
