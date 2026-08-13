"""Standalone import-boundary checker for app/'s layering rules.

No lint/pre-commit infra exists in this repo (no .flake8, no ruff config,
no pre-commit hooks) — run this by hand after touching app/core/,
app/interface/, app/plugins/, or app/plugin_api/:

    python developer/app/check_import_boundaries.py

Enforces (see developer/app/... plan notes / root CLAUDE.md's "Merged-repo
structure" for the app/ layout this assumes):

- app/plugins/**  must never import `core.*` or `interface.*` — plugins go
                    through plugin_api instead (plugin_api/__init__.py
                    re-exports every core/ type via core_api, and every
                    interface/ UI symbol (shared widgets, theme helpers,
                    LOCAL_REPOSITORY) via interface_api, that a plugin
                    needs). interface/ is fully closed as of the
                    interface_api refactor — a plugin file never writes
                    `from interface.xxx import yyy`, only
                    `from plugin_api import yyy`.
- app/core/**      must never import `interface.*`, `plugins.*`,
                    `core_api.*`, or `plugin_api.*` — core is the
                    innermost layer.
- app/plugin_api/** must never import `interface.*` or `plugins.*` — only
                    `core`/`core_api`/`interface_api` (+ stdlib/third-party/
                    PySide6). Importing `interface_api.*` (not `interface.*`
                    itself) is how plugin_api/__init__.py re-exports UI
                    symbols to plugins — see app/interface_api/__init__.py.
- app/interface/** must never import `core.*` directly — ONLY enforced
                    once app/core_api/ exists (Phase B of the core_api/
                    plugin_api refactor; today, before Phase B, interface/
                    still legitimately imports core.* directly, so this
                    rule is skipped until core_api/ is real).
- app/launcher.py  must never import `interface.*` directly — ONLY
                    enforced once app/interface_api/ exists (the
                    interface_api refactor; launcher.py goes through
                    interface_api instead, same relationship plugin_api
                    already has with core_api).

Exits non-zero and prints one `file:line: message` per violation.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent.parent / "app"


def _iter_py_files(root: Path):
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*.py")):
        # Skip __pycache__ and anything under a repo plugin's own
        # cache/plugins/ clone if ever pointed there by mistake.
        if "__pycache__" in path.parts:
            continue
        yield path


def _imported_top_level_modules(path: Path) -> list[tuple[int, str]]:
    """Returns (lineno, top_level_module_name) for every import in `path`,
    at any nesting depth (function-local/deferred imports included, since
    launcher.py and plugin_api.py's cloud_sync import are deliberately
    deferred but still subject to the same boundary rules)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        print(f"{path}: SyntaxError while parsing for import check: {exc}")
        return []

    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((node.lineno, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import — can't cross a top-level package boundary
            if node.module:
                found.append((node.lineno, node.module.split(".")[0]))
    return found


def _check(root: Path, *, banned: set[str], label: str) -> list[str]:
    violations = []
    for path in _iter_py_files(root):
        rel = path.relative_to(APP_ROOT.parent)
        for lineno, module in _imported_top_level_modules(path):
            if module in banned:
                violations.append(f"{rel}:{lineno}: {label} imports '{module}' — not allowed here")
    return violations


def _check_file(path: Path, *, banned: set[str], label: str) -> list[str]:
    if not path.is_file():
        return []
    violations = []
    rel = path.relative_to(APP_ROOT.parent)
    for lineno, module in _imported_top_level_modules(path):
        if module in banned:
            violations.append(f"{rel}:{lineno}: {label} imports '{module}' — not allowed here")
    return violations


def main() -> int:
    violations: list[str] = []

    violations += _check(
        APP_ROOT / "plugins",
        banned={"core", "interface"},
        label="app/plugins/",
    )
    violations += _check(
        APP_ROOT / "core",
        banned={"interface", "plugins", "core_api", "plugin_api"},
        label="app/core/",
    )
    violations += _check(
        APP_ROOT / "plugin_api",
        banned={"interface", "plugins"},
        label="app/plugin_api/",
    )

    if (APP_ROOT / "core_api").is_dir():
        # Phase B of the core_api/plugin_api refactor has started — now
        # interface/ must go through core_api instead of core.* directly.
        violations += _check(
            APP_ROOT / "interface",
            banned={"core"},
            label="app/interface/",
        )
    else:
        print("(app/core_api/ doesn't exist yet — skipping the interface/ -> core.* "
              "check; that's Phase B of the core_api/plugin_api refactor.)")

    if (APP_ROOT / "interface_api").is_dir():
        # interface_api refactor has started — launcher.py must go through
        # interface_api instead of interface.* directly.
        violations += _check_file(
            APP_ROOT / "launcher.py",
            banned={"interface"},
            label="app/launcher.py",
        )
    else:
        print("(app/interface_api/ doesn't exist yet — skipping the launcher.py -> "
              "interface.* check; that's the interface_api refactor.)")

    if violations:
        print(f"\n{len(violations)} import-boundary violation(s):")
        for v in violations:
            print(f"  {v}")
        return 1

    print("No import-boundary violations found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
