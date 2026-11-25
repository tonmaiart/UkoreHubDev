"""portal/ and app/ can't import each other, so the literals they hand-shake
over (stdout markers, the singleton pipe name, the eagerly-pulled blob
list, ...) are duplicated on each side — this pins every pair together by
parsing both files, without importing either."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _constant(relative_path: str, name: str):
    tree = ast.parse((REPO_ROOT / relative_path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {relative_path}")


@pytest.mark.parametrize(
    ("app_file", "app_name", "portal_file", "portal_name"),
    [
        ("app/launcher.py", "SINGLETON_SERVER_NAME", "portal/main.py", "_APP_SINGLETON_SERVER_NAME"),
        ("app/launcher.py", "_APP_STATUS_PREFIX", "portal/main.py", "_APP_STATUS_PREFIX"),
        ("app/launcher.py", "_APP_READY_MARKER", "portal/main.py", "_APP_READY_MARKER"),
        ("app/launcher.py", "_SHARED_FIXED_BLOBS", "portal/cloud_sync.py", "_FIXED_BLOBS"),
        (
            "app/interface/main_window.py",
            "_SHOW_PROJECT_PICKER_MARKER",
            "portal/main.py",
            "_SHOW_PROJECT_PICKER_MARKER",
        ),
        (
            "app/plugins/core/project_editor/plugin.py",
            "_EXTERNAL_PLUGINS_PLUGIN_ID",
            "portal/plugin_update.py",
            "_EXTERNAL_PLUGINS_KEY",
        ),
    ],
)
def test_portal_and_app_constants_match(app_file, app_name, portal_file, portal_name):
    assert _constant(app_file, app_name) == _constant(portal_file, portal_name)
