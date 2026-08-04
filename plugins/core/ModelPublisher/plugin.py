from __future__ import annotations

TOOL_ID = "model_publisher"
TOOL_LABEL = "ModelPublisher"
# Convention-only string match with plugins/core/maya_launcher/plugin.py
# — both resolve to the same data/plugins/core/maya_launcher_env_bridge.json
# via PluginConfigStore, no coupling API needed. See that plugin's README
# for the full "contributions"/"labels" shape this writes into. Relies on
# plugins/core/MayaToolkit (UkoreMaya.core.Pipeline) and
# plugins/core/PublishApi also being enabled — not imported directly,
# just expected to be on the same merged PYTHONPATH at Maya launch time.
MAYA_ENV_BRIDGE_PLUGIN_ID = "maya_launcher_env_bridge"
ANY_VERSION = "*"


def register(api) -> None:
    tool_root = api.app_root / "plugins" / "core" / "ModelPublisher"

    bridge = api.plugin_config_store(MAYA_ENV_BRIDGE_PLUGIN_ID, shared=True)
    contributions = bridge.get("contributions", {})
    contributions[TOOL_ID] = {
        "PYTHONPATH": {ANY_VERSION: [str(tool_root / "maya-scripts")]},
    }
    bridge.set("contributions", contributions)
    labels = bridge.get("labels", {})
    labels[TOOL_ID] = TOOL_LABEL
    bridge.set("labels", labels)
