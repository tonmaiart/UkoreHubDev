"""Entry point compiled by PyInstaller into UkoreHub.exe.

Locates launcher.py and this exe's own repo root, then hands off to
updater.main() (same folder — see updater.py) which shows a progress window,
checks/installs Python + git + git-lfs, brings the repo up to date with
origin/main (bootstrapping it into a real git clone first if it's a plain
ZIP extract with no .git directory), then spawns launcher.py detached and
returns. This process never supervises launcher.py after that — self-update's
os.execv() inside the spawned Python process is entirely unaffected by how
it was started.

Deliberately minimal: all the actual logic lives in updater.py, a sibling,
stdlib-only module (see its own docstring for why it avoids importing
launcher.py/core/) — PyInstaller bundles both since exe_entry.py imports
updater.py, but nothing beyond their combined stdlib-only import graph.
"""
import ctypes
import sys
from pathlib import Path

import updater


def _own_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Frozen: sys.executable is the compiled exe itself, NOT a real
        # python.exe — never derive the interpreter from this.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _fatal(message: str) -> None:
    ctypes.windll.user32.MessageBoxW(None, message, "UkoreHub", 0x10)  # MB_ICONERROR
    sys.exit(1)


def main() -> None:
    repo_root = _own_dir()
    launcher_path = repo_root / "launcher.py"
    if not launcher_path.is_file():
        _fatal(f"launcher.py not found next to UkoreHub.exe:\n{launcher_path}")

    updater.main(repo_root)


if __name__ == "__main__":
    main()
