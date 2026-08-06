# packaging/

Admin-only dev/ops tooling for building `UkoreHub.exe`, a thin native
launcher artists can double-click or pin to the taskbar instead of running
`python launcher.py` from a terminal. Not imported by the running app —
run manually by an admin, only when rebranding the icon or changing
`exe_entry.py`/`updater.py` themselves.

- `build_exe.py` — run this to (re)build `UkoreHub.exe` at the repo root.
  Installs `pyinstaller` and `keyring` into the current environment if
  missing (this script's own concern only — neither is added to
  launcher.py's dependency bootstrap). `--icon`/`--name` CLI args, defaults
  to `icon.ico`/"UkoreHub".
- `exe_entry.py` — the tiny script PyInstaller compiles. Locates
  `launcher.py`/the repo root next to wherever the exe is actually running
  from (never derives paths from its own frozen `sys.executable`), then
  hands off to `updater.main()`.
- `updater.py` — everything `exe_entry.py` used to do inline, now with a
  real `tkinter` progress window (stdlib, so it ships inside the frozen exe
  without needing a heavier UI toolkit bundled this early — a PySide6
  version of just this stage came out to ~50MB, mostly Qt6Core/Qt6Gui/
  Qt6Widgets + the software-OpenGL fallback DLL, against tkinter's
  ~5-8MB), plus:
  - **Prerequisite checks + self-update, in this order**: checks `git` is
    on PATH first (required — the update step right after it needs `git`
    to run) — if missing, shows a "Download" button linking straight to
    the official Git-for-Windows installer and stops there; no more
    silent `winget` auto-install. With `git` confirmed present, brings the
    repo root up to date with `origin/main` *before* checking anything
    else, so a stale checkout never gets skipped — via `git fetch`+`git
    pull` if it's already a clone, or via `git init`+`git remote
    add`+`git fetch`+`git checkout` first if it's a plain folder with no
    `.git` (e.g. someone used GitHub's "Download ZIP" instead of `git
    clone`). Only after that does it check for a `python(w)` interpreter
    (same Download-button treatment, linking to the python.org installer,
    since it's needed to spawn `launcher.py`) and `git-lfs` (optional —
    warns and continues if missing).
  - **GitHub login**: the sole place login happens now — `interface/login/`
    was deleted entirely from the running app. `_LoginDialog` (a `Toplevel`)
    runs the OAuth device-flow (`core/github/auth.py`'s
    `request_device_code`/`poll_for_token`/`fetch_username` directly, on a
    background thread) and caches the token via `core/github/token_store.py`'s
    `TokenStore`. Skipped if a token's already cached (just shows "Signed
    in as ..." briefly with a "Switch Account" button — the only way to
    log out now, since `MainWindow` has no in-app login UI of its own to
    fall back to; clicking it clears the token and reruns this step).
  - Finally spawns `launcher.py` detached and returns. On a fatal failure
    (no `git`, update failed) the window shows the error and stays open
    instead of closing silently.

  Both files are **deliberately self-contained (stdlib only, including
  `tkinter`)** rather than importing from `launcher.py` or most of `core/`
  — PyInstaller only bundles what this pair's own import graph reaches,
  and the rest of UkoreHub is meant to stay plain `.py` files reached via
  `git pull`, not baked into the exe. This is why
  `check_git_prerequisite`/`check_git_lfs_prerequisite` in `updater.py`
  are near-duplicates of `launcher.py`'s own copies (still
  needed there for the `python launcher.py` direct entry point, which
  bypasses this exe and its update/login step entirely) rather than a
  shared import — same reasoning for the git bootstrap/update logic vs.
  `core/self_update.py`/`core/git_service.py`. `core/github/auth.py`,
  `core/github/token_store.py`, and `core/store.py` are the one deliberate
  exception: confirmed stdlib-only, and since the in-app login UI is gone,
  this module is their only consumer for the OAuth flow — importing them
  directly avoids duplicating that logic rather than any general rule
  against importing `core/`.
- `icon.ico` — the icon baked into `UkoreHub.exe` (swap this file and rerun
  `build_exe.py` to rebrand). Git-tracked. `launcher.py` also loads this
  same file directly (`QApplication.setWindowIcon`) — `UkoreHub.exe` only
  owns this icon for the instant it exists before handing off to a plain
  `python(w).exe` process (see `exe_entry.py`), which would otherwise show
  Windows' generic Python icon in the taskbar/title bar without that.

See root `README.md`'s "Running" section for how artists use the built
exe, and `.gitignore` for why `build/` and `*.spec` (PyInstaller's
regenerable intermediates) are excluded while the final `.exe` is not.
