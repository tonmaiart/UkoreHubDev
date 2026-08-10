"""Admin-only tool: builds UkoreHubLauncher.exe from exe_entry.py.

Run after rebranding icon.ico, or after changing exe_entry.py/updater.py
themselves — NOT part of routine app development, which lives in this
repo's app/ and reaches artists via git pull / Update and Restart as plain
.py files (see developer/launcher/README.md for the split).

Installs pyinstaller into the CURRENT environment only if missing, kept
deliberately separate from app/launcher.py's REQUIRED_PACKAGES bootstrap.
"""
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path

# This file lives at developer/launcher/launcher_build/ — three levels
# under the repo root (unlike the old standalone UkoreHubLauncherDev repo,
# where launcher_build/ was one level under its own root) — so REPO_ROOT
# has to walk up three parents, not one. distpath stays REPO_ROOT (the exe
# still lands at the repo root, next to app/), but workpath/specpath move
# to developer/launcher/build/ instead of a bare build/ at the repo root,
# to keep PyInstaller's intermediates grouped with the rest of the
# dev-only launcher tooling.
BUILD_DIR_ROOT = Path(__file__).resolve().parent
DEV_LAUNCHER_DIR = BUILD_DIR_ROOT.parent
REPO_ROOT = DEV_LAUNCHER_DIR.parent.parent
BUILD_WORK_DIR = DEV_LAUNCHER_DIR / "build"
DEFAULT_ICON = BUILD_DIR_ROOT / "icon.ico"


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return
    print("build_exe.py: installing PyInstaller into the current environment...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)


def ensure_build_dependencies() -> None:
    """updater.py (bundled into the exe alongside exe_entry.py — see
    build()) uses keyring for the GitHub token cache (tkinter itself is
    stdlib, ships with Python, needs nothing installed) — needs to be
    importable in *this* environment for PyInstaller's analysis to bundle
    it. Installed here rather than added to launcher.py's own
    REQUIRED_PACKAGES bootstrap — that one governs the already-running
    app's environment, not this admin-only build step's."""
    if importlib.util.find_spec("keyring") is not None:
        return
    print("build_exe.py: installing missing build dependency 'keyring>=24.0'...")
    subprocess.run([sys.executable, "-m", "pip", "install", "keyring>=24.0"], check=True)


def build(icon: Path, name: str) -> Path:
    entry = Path(__file__).resolve().parent / "exe_entry.py"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--noconsole",
        # PyInstaller's own build cache can silently skip re-bundling a
        # sibling module that changed without updater.py itself changing —
        # e.g. editing r2_credentials.py (real key rotation) without
        # touching updater.py produced a byte-identical, stale exe here
        # once. --clean forces a full re-analysis every time; this script
        # is admin-only/infrequent, so the extra build time is cheap
        # insurance against silently shipping stale-baked credentials.
        "--clean",
        f"--name={name}",
        f"--distpath={REPO_ROOT}",
        f"--workpath={BUILD_WORK_DIR}",
        f"--specpath={BUILD_WORK_DIR}",
    ]
    if icon.is_file():
        cmd.append(f"--icon={icon}")
    else:
        print(f"build_exe.py: warning — icon not found at {icon}, building without a custom icon.")
    cmd.append(str(entry))

    subprocess.run(cmd, check=True, cwd=str(REPO_ROOT))
    return REPO_ROOT / f"{name}.exe"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icon", type=Path, default=DEFAULT_ICON, help="Path to a .ico file")
    parser.add_argument("--name", default="UkoreHubLauncher", help="Output exe base name")
    args = parser.parse_args()

    ensure_pyinstaller()
    ensure_build_dependencies()
    exe_path = build(args.icon, args.name)
    print(f"build_exe.py: built {exe_path}")


if __name__ == "__main__":
    main()
