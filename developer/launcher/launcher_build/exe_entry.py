"""Entry point compiled by PyInstaller into UkoreHubLauncher.exe.

Locates this exe's own repo root (this launcher repo, UkoreHubLauncher —
see README.md), then hands off to updater.main() (same folder — see
updater.py) which shows a progress window, self-updates this launcher repo,
bootstraps/updates the nested app/ clone (the actual UkoreHub app repo),
checks/installs Python + git + git-lfs, then spawns app/launcher.py
detached and returns. This process never supervises launcher.py after
that — self-update's os.execv() inside the spawned Python process is
entirely unaffected by how it was started.

Deliberately minimal: all the actual logic lives in updater.py, a sibling,
stdlib-only module (see its own docstring for why it avoids importing the
app repo's code directly) — PyInstaller bundles both since exe_entry.py
imports updater.py, but nothing beyond their combined stdlib-only import
graph.
"""
import sys
from pathlib import Path

import updater


def _own_dir() -> Path:
    if getattr(sys, "frozen", False):
        # Frozen: sys.executable is the compiled exe itself, NOT a real
        # python.exe — never derive the interpreter from this.
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> None:
    # Unlike before the split, launcher.py isn't expected to exist yet on a
    # first run — updater.main() bootstraps the nested app/ clone (which is
    # where launcher.py lives) itself.
    updater.main(_own_dir())


if __name__ == "__main__":
    main()
