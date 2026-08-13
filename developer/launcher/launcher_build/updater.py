"""UI/logic behind UkoreHubLauncher.exe (see exe_entry.py, the PyInstaller compile
target that just calls main() here).

This repo (UkoreHubLauncher) is deliberately separate from the app repo
(UkoreHub, a.k.a. "UkoreHubRelease") artists actually run — see this
repo's README. `UkoreHubLauncher.exe` lives and self-updates here; `launcher.py`
and everything under `core/`/`interface/`/`plugins/` live in a nested
`app/` clone this module bootstraps/updates independently. Splitting them
means an ordinary app release can never again try to overwrite the exe
file that's busy executing this very code (see UkoreHubDev's
`ukorehub-launcher` skill for the bug this eliminates for the frequent
case) — only a rare
launcher-repo release (rebranding the icon, changing this file) still
needs the `_relocate_self_exe` rename-aside trick below.

Handles everything that has to happen before launcher.py can even be
spawned, in this order: check that git is on PATH (required — shows a
"Download" button linking to the official installer and stops if it's
missing, no silent auto-install anymore), self-update this launcher repo
(rare — bootstrapping it into a real git clone first if it's a plain ZIP
extract with no .git directory), then bootstrap/update the nested `app/`
clone the same way, check that Python is on PATH (also required, same
Download-button treatment, used to spawn launcher.py), check git-lfs
(optional — warns and continues if missing, no auto-install), then GitHub
login — this module is the sole place login happens and the GitHub token
gets cached (TokenStore); there is no in-app login UI. Finally spawns
launcher.py (from `app/`) detached, same hand-off as before.

Dev mode: when this exe is run from inside the merged UkoreHubDev dev repo
instead of a real artist install (detected by `_is_dev_checkout` — a
`developer/` folder next to the exe, which no release checkout ever has),
both self-update steps above are skipped entirely and `app/` is used as-is
— see `_is_dev_checkout`/`_do_prelaunch_work`. This is what lets you
double-click the exe here to exercise the real pre-launch UX (prereq
checks, GitHub login, workspace picker) against your local `app/` edits
without it hard-resetting either this repo or `app/` against a release
remote.

Uses `tkinter` (stdlib, ships with every python.org Windows install that
includes Tcl/Tk, the default) rather than PySide6: a PySide6 build of just this pre-launch stage came out to ~50MB
(Qt6Core/Qt6Gui/Qt6Widgets + the opengl32sw.dll software-rasterizer
fallback alone are ~45MB, largely unavoidable even after excluding every
unrelated Qt submodule — see git history around
`build_exe.py`'s now-removed `_UNUSED_PYSIDE6_MODULES`
list), against tkinter's ~5-8MB (`tcl86t.dll`/`tk86t.dll` + script
library). The device-flow login dialog (`_LoginDialog` below) is a
tkinter `Toplevel` port of the old PySide6 version, same shape.

Import discipline: the prerequisite-check helpers and the git bootstrap/
update logic below are intentionally near-duplicates of the app repo's
launcher.py's and core/self_update.py's respectively (kept minimal and
self-contained so this repo never needs the app repo cloned locally just
to build). GitHub login goes one step further: `core/exceptions.py`,
`core/models.py`, `core/paths.py`, `core/theme.py`, `core/store.py`, and
`core/github/` under this repo's own `core/` are **vendored copies** of
the app repo's identically-named files (confirmed stdlib-only — auth.py
uses urllib only; token_store.py imports keyring lazily inside
try/except with a JSON-file fallback), not a cross-repo import, since a
separate repo has no way to import the app repo's package directly. A
change to the real ones in the app repo (GitHub OAuth flow, token
storage, local/system config schema) needs to be manually mirrored here
too if it should also apply to this pre-launch login screen.
"""
from __future__ import annotations

import contextlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.exceptions import GitHubAuthError
from core.github import auth as github_auth
from core.github.token_store import TokenStore, TokenStoreFallbackUsed
from core.store import LocalConfigStore, SystemConfigStore

# The shared Cloudflare R2 key for cloud sync (app/core/vcs/cloud_sync.py) —
# baked into this exe at build time via a gitignored sibling module (see
# r2_credentials.example.py's docstring for the "copy, fill in, rebuild"
# steps), never committed here or read from any JSON store. Every value is
# None on a checkout that hasn't created r2_credentials.py yet (e.g. a
# fresh dev machine) — _launch() below only sets the UKOREHUB_R2_* env vars
# when they're actually present, so app/launcher.py's own _build_cloud_sync
# falls back to local-only, same as "not configured" today.
try:
    from r2_credentials import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
except ImportError:
    R2_ACCOUNT_ID = R2_ACCESS_KEY_ID = R2_SECRET_ACCESS_KEY = R2_BUCKET_NAME = None

# The app repo (what `app/` clones/updates) — unchanged from before the split.
UKOREHUB_REMOTE_URL = "https://github.com/tonmaiart/UkoreHub.git"
UKOREHUB_BRANCH = "main"
# This launcher repo itself — what `repo_root` (UkoreHubLauncher.exe's own folder)
# self-updates from. Rare: only changes on an icon rebrand or an edit to
# this file/exe_entry.py/build_exe.py.
LAUNCHER_REMOTE_URL = "https://github.com/tonmaiart/UkoreHubLauncher.git"
LAUNCHER_BRANCH = "main"
# Name of the nested app clone inside repo_root — gitignored by this repo
# (see .gitignore) since it's an independent git working tree, not part of
# this repo's own tracked files.
APP_DIRNAME = "app"
GIT_DOWNLOAD_URL = "https://git-scm.com/install/windows"
PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/pymanager/python-manager-26.3.msix"
# Public GitHub OAuth App Client ID (Device Flow has no client secret, so
# this isn't sensitive) — a Launcher-baked fallback for when the
# studio-shared data/system_config.json hasn't been cloud-synced/
# configured yet (see _start_login_flow), which otherwise blocks login on
# a fresh machine before launcher.py ever gets to run cloud_sync itself.
# Setting > Common > GitHub OAuth Client ID (data/system_config.json)
# still wins whenever a studio admin has actually set one there.
DEFAULT_GITHUB_CLIENT_ID = "Ov23liCPza6KiJ7MWZbc"

_NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_ICON_PATH = Path(__file__).resolve().parent / "icon.ico"


class UpdaterError(Exception):
    pass


# -- prerequisite checks (presence only — no auto-install; see the
# "Download" button in _UpdaterWindow for what happens when one is missing)
# (near-duplicate of launcher.py's) --


def check_git_prerequisite() -> bool:
    return shutil.which("git") is not None


def check_git_lfs_prerequisite() -> bool:
    return shutil.which("git-lfs") is not None


def find_python_interpreter() -> str | None:
    return shutil.which("pythonw") or shutil.which("python")


# -- git bootstrap/update (near-duplicate of core/self_update.py's) --------


def _non_interactive_env() -> dict:
    """Same reasoning as core/git_service.py's identical helper: fail fast
    with a visible error instead of hanging forever waiting for a
    username/password/passphrase prompt nobody is watching."""
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    ssh_command = env.get("GIT_SSH_COMMAND", "ssh")
    env["GIT_SSH_COMMAND"] = f"{ssh_command} -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
    return env


def _run_git(args: list[str], cwd: Path) -> str:
    git_executable = shutil.which("git") or "git"
    result = subprocess.run(
        [git_executable, *args],
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=_non_interactive_env(),
        creationflags=_NO_WINDOW_FLAGS,
    )
    if result.returncode != 0:
        raise UpdaterError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def is_git_repo(repo_root: Path) -> bool:
    return (repo_root / ".git").exists()


def bootstrap_git_repo(repo_root: Path, remote_url: str, branch: str) -> None:
    """Turns a plain folder (e.g. a GitHub "Download ZIP" extract, which has
    no .git directory at all) into a real git working tree tracking
    remote_url/branch, in place — so every later run (and the in-app "Update
    and Restart" button) can use ordinary git fetch/pull from then on."""
    _run_git(["init"], cwd=repo_root)
    _run_git(["remote", "add", "origin", remote_url], cwd=repo_root)
    _run_git(["fetch", "origin", branch], cwd=repo_root)
    try:
        _run_git(["checkout", "-B", branch, "--track", f"origin/{branch}"], cwd=repo_root)
    except UpdaterError:
        # Fresh extract's files conflict with git's view of the tracked
        # tree (e.g. line-ending differences) — force since there's no local
        # history here to lose, only a plain file extract.
        _run_git(["checkout", "-f", "-B", branch, "--track", f"origin/{branch}"], cwd=repo_root)


def _running_self_exe_path(repo_root: Path) -> Path | None:
    """Path of the exe currently running this process, if we ARE
    UkoreHubLauncher.exe launched from repo_root — None for `python updater.py`/
    pytest, where nothing needs relocating and git can touch the working
    tree freely."""
    if not getattr(sys, "frozen", False):
        return None
    exe_path = repo_root / "UkoreHubLauncher.exe"
    try:
        return exe_path if Path(sys.executable).resolve() == exe_path.resolve() else None
    except OSError:
        return None


def _cleanup_stale_relocated_exe(repo_root: Path) -> None:
    """Best-effort delete of a previous run's renamed-aside exe that never
    got cleaned up (e.g. the process was killed mid-update) — safe to retry
    since by the time a new UkoreHubLauncher.exe is running, nothing else should
    still have the old one open."""
    for stale in repo_root.glob("UkoreHubLauncher.exe.old-*"):
        try:
            stale.unlink()
        except OSError:
            pass


@contextlib.contextmanager
def _relocate_self_exe(repo_root: Path):
    """Windows refuses to unlink/overwrite the .exe file that's currently
    executing (`unable to unlink old 'UkoreHubLauncher.exe': Invalid argument` from
    `git checkout`/`git pull`), but it does allow renaming it — a running
    process keeps its open file handle regardless of what the directory
    entry is called, the same trick self-updating browsers use. Move
    UkoreHubLauncher.exe out of the way before any git operation that might touch
    it, so checkout/pull can write a fresh one at that path unobstructed;
    delete the leftover on success, or put it back if the update failed so
    "continue with the current version" (see the caller's error dialog)
    stays true.

    Renaming aside happens unconditionally (before the caller even knows
    whether a pull will run), but git only ever rewrites this path when the
    pull's incoming diff actually touches the exe blob — not on an
    already-up-to-date no-op pull, and not on a pull that changes only
    unrelated files. So "did git actually recreate exe_path" has to be
    checked explicitly on the success path too, not just the exception
    path — otherwise the ordinary case (nothing to update) permanently
    strands the running exe under its .old-<pid> name once Windows refuses
    the unlink."""
    exe_path = _running_self_exe_path(repo_root)
    if exe_path is None:
        yield
        return
    _cleanup_stale_relocated_exe(repo_root)
    relocated = exe_path.with_name(f"UkoreHubLauncher.exe.old-{os.getpid()}")
    try:
        exe_path.rename(relocated)
    except OSError as exc:
        raise UpdaterError(f"could not prepare self-update: {exc}") from exc
    try:
        yield
    except Exception:
        if not exe_path.exists():
            relocated.rename(exe_path)
        raise
    else:
        if not exe_path.exists():
            # Nothing rewrote this path (no pull ran, or the pull didn't
            # touch the exe blob) — put the running exe back where
            # double-clicking expects to find it, exactly like the
            # failure path above.
            relocated.rename(exe_path)
            return
        try:
            relocated.unlink()
        except OSError:
            pass


# Per-machine / in-flight paths `git clean -fd` below must never sweep —
# hardcoded here (as `git clean -e` excludes) rather than relying on an
# on-disk .gitignore, since the release repo this runs against ships
# without one (see CLAUDE.md's "release repo never carries dev-only
# files"). Mirrors this repo's own .gitignore 1:1, so the clean below
# behaves the same whether or not a .gitignore happens to be present in
# the checkout it's running against. See UkoreHubDev's `ukorehub-launcher`
# skill for the incident this fixes — a customer machine that had no .gitignore
# in its checkout (the release repo) hit `git clean -fd` deleting both
# launcher_config.json (re-triggering the workspace prompt on every launch)
# and the running exe's own renamed-aside `.old-<pid>` file (aborting the
# self-update that would have delivered the fix, since `clean` ran before
# `reset --hard`).
_CLEAN_PROTECTED_PATTERNS = [
    ".venv/",
    "__pycache__/",
    "*.pyc",
    "/app/",
    "/workspace/",
    "/launcher_config.json",
    "/build/",
    "*.spec",
    "/UkoreHubLauncher.exe.old-*",
]


def _clean_untracked(repo_root: Path) -> None:
    args = ["clean", "-fd"]
    for pattern in _CLEAN_PROTECTED_PATTERNS:
        args.extend(["-e", pattern])
    try:
        _run_git(args, cwd=repo_root)
    except UpdaterError:
        # Best-effort: some other stray untracked file `git clean` can't
        # remove (locked by antivirus, a lingering handle, etc.) must never
        # block the `reset --hard` right after this — that's the operation
        # that actually delivers a fix to this machine.
        pass


def ensure_up_to_date(
    repo_root: Path,
    remote_url: str = UKOREHUB_REMOTE_URL,
    branch: str = UKOREHUB_BRANCH,
) -> None:
    """remote_url/branch only matter for the fresh-bootstrap case (a plain
    ZIP extract with no existing branch/upstream to speak of). Once it's a
    real clone, this follows whatever branch is actually checked out and
    its own configured upstream (@{u}) — same as the app repo's
    core/self_update.py's check_for_update/pull_update — rather than
    assuming everyone is on `branch`. An admin checkout intentionally
    sitting on `dev` must not get silently pulled onto `main`.

    Forces the working tree to exactly match upstream (fetch + clean -fd +
    reset --hard) instead of `git pull` (a merge, which git refuses the
    moment anything local — a modified tracked file, or an untracked file
    sitting where an incoming commit wants to add one — is in the way).
    There is nothing in either working tree worth a merge conflict over:
    per-machine files (cache/, storage/) live outside both these
    directories entirely (see _UpdaterWindow), and the shared registries
    under the app repo's data/ are re-synced from Cloudflare R2 on every
    launch (core/vcs/cloud_sync.py in the app repo) — the git-tracked copy
    is a fallback, not the source of truth, so overwriting it here is safe. The
    clean step (_clean_untracked) only ever removes files this repo
    genuinely doesn't want lying around — never the per-machine/in-flight
    ones above.

    Used for two different directories with different risk profiles: this
    launcher repo's own root (repo_root passed to _UpdaterWindow) has
    UkoreHubLauncher.exe git-tracked in it, so _relocate_self_exe actually does
    something there — the exe currently running this code would otherwise
    get overwritten mid-reset. Called again against the nested `app/`
    directory, _relocate_self_exe is a no-op (UkoreHubLauncher.exe was never part
    of that working tree to begin with), so this same function is safe to
    reuse for both without any special-casing."""
    with _relocate_self_exe(repo_root):
        if not is_git_repo(repo_root):
            bootstrap_git_repo(repo_root, remote_url, branch)
            return
        _run_git(["fetch"], cwd=repo_root)
        local_head = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
        upstream_head = _run_git(["rev-parse", "@{u}"], cwd=repo_root)
        if local_head != upstream_head:
            _clean_untracked(repo_root)
            _run_git(["reset", "--hard", upstream_head], cwd=repo_root)


def _is_dev_checkout(repo_root: Path) -> bool:
    """True when this exe is running out of the merged UkoreHubDev dev repo
    rather than a real artist install — release repos never carry a
    developer/ folder (stripped by developer/release_app.ps1 /
    developer/release_launcher.ps1 before anything is published), so its
    presence next to the exe is the signal to use. In that case repo_root
    is this dev repo's own git working tree (not the UkoreHubLauncher
    release repo) and app_root (app/) is a plain subfolder of it, not an
    independent clone of the UkoreHub release repo — ensure_up_to_date must
    never run against either (see _do_prelaunch_work)."""
    return (repo_root / "developer").exists()


# -- GitHub login (tkinter port of the old interface/login/ in-app gate) ---


class _LoginDialog:
    """Modal-ish Toplevel wrapping the device-flow login (device code +
    verification URL + copy button + progress), reusing
    core/github/auth.py's request_device_code/poll_for_token/fetch_username
    directly. The polling runs on a background thread (network calls —
    can't block the Tk event loop); a queue.Queue is how it reports back,
    same pattern as the main window below."""

    def __init__(self, parent: tk.Misc, client_id: str | None):
        self.username: str | None = None
        self.token: str | None = None

        self.top = tk.Toplevel(parent)
        self.top.title("GitHub Login")
        self.top.geometry("400x220")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.instructions_var = tk.StringVar(value="Starting GitHub login...")
        ttk.Label(self.top, textvariable=self.instructions_var, wraplength=360, padding=(16, 12, 16, 4)).pack(fill="x")

        self.code_var = tk.StringVar(value="")
        ttk.Label(self.top, textvariable=self.code_var, font=("Segoe UI", 20, "bold")).pack(pady=4)

        self.copy_button = ttk.Button(self.top, text="Copy Code", command=self._copy_code, state="disabled")
        self.copy_button.pack(pady=4)

        self.progress = ttk.Progressbar(self.top, mode="indeterminate")
        self.progress.pack(fill="x", padx=16, pady=8)
        self.progress.start(12)

        ttk.Button(self.top, text="Cancel", command=self._on_cancel).pack(pady=(0, 12))

        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._worker = threading.Thread(target=self._run_auth, args=(client_id,), daemon=True)
        self._worker.start()
        self.top.after(100, self._poll_queue)

    def _run_auth(self, client_id: str | None) -> None:
        try:
            if not client_id:
                raise GitHubAuthError(
                    "GitHub Client ID not configured (data/system_config.json) — ask a studio admin."
                )
            device_code_response = github_auth.request_device_code(client_id)
            self._queue.put(("code", device_code_response.user_code, device_code_response.verification_uri))
            webbrowser.open(device_code_response.verification_uri)
            token = github_auth.poll_for_token(
                client_id,
                device_code_response.device_code,
                device_code_response.interval,
                device_code_response.expires_in,
            )
            username = github_auth.fetch_username(token)
            self._queue.put(("done", username, token))
        except GitHubAuthError as exc:
            self._queue.put(("failed", str(exc)))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]
                if kind == "code":
                    _, code, verification_uri = item
                    self.instructions_var.set(
                        f"Your browser should have opened to {verification_uri} — enter this code there:"
                    )
                    self.code_var.set(code)
                    self.copy_button.configure(state="normal")
                elif kind == "done":
                    _, username, token = item
                    self.username = username
                    self.token = token
                    self.top.destroy()
                    return
                elif kind == "failed":
                    _, message = item
                    self.progress.stop()
                    self.instructions_var.set(f"Login failed: {message}")
                    return
        except queue.Empty:
            pass
        if self.top.winfo_exists():
            self.top.after(100, self._poll_queue)

    def _copy_code(self) -> None:
        self.top.clipboard_clear()
        self.top.clipboard_append(self.code_var.get())

    def _on_cancel(self) -> None:
        self.top.destroy()

    def wait(self) -> bool:
        """Blocks (via Tk's nested-event-loop wait_window, not a real
        thread block) until the dialog closes, either from a successful
        login (see _poll_queue's "done" branch) or Cancel/window-close."""
        self.top.wait_window()
        return self.token is not None


# -- workspace location (first-run prompt) ----------------------------------

# Lives directly at repo_root, never inside cache/ or the workspace folder
# itself — both of those are *derived from* this setting (see
# ensure_workspace_dir), so the setting can't live inside either without a
# chicken-and-egg problem. Per-machine, so gitignored (see .gitignore).
LAUNCHER_CONFIG_FILENAME = "launcher_config.json"


def _load_workspace_root(repo_root: Path) -> str | None:
    config_path = repo_root / LAUNCHER_CONFIG_FILENAME
    if not config_path.exists():
        return None
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data.get("workspace_root") or None


def _save_workspace_root(repo_root: Path, workspace_root: str) -> None:
    config_path = repo_root / LAUNCHER_CONFIG_FILENAME
    config_path.write_text(json.dumps({"workspace_root": workspace_root}, indent=2), encoding="utf-8")


def ensure_workspace_dir(repo_root: Path, parent: tk.Tk) -> Path:
    """First run only: asks where to put the Workspace folder — it'll hold
    cache/ (login token, local settings) and storage/ (cloned repos), both
    per-machine (see _UpdaterWindow) — and remembers the answer in
    launcher_config.json at repo_root so this never asks again on this
    machine. Cancelling the picker (rather than looping/blocking forever)
    falls back to a workspace/ folder right next to the exe — still a
    valid, working choice, just not one that survives an OS reinstall the
    way a separate drive would."""
    stored = _load_workspace_root(repo_root)
    if stored:
        return Path(stored)
    messagebox.showinfo(
        "UkoreHub Setup",
        "Choose a folder for your UkoreHub Workspace.\n\n"
        "This is where your cloned repos and local app data will live — "
        "pick a drive with enough free space. You won't be asked again.",
        parent=parent,
    )
    chosen = filedialog.askdirectory(
        parent=parent,
        title="Choose UkoreHub Workspace Folder",
        initialdir=str(Path.home()),
        mustexist=False,
    )
    workspace_dir = Path(chosen) if chosen else repo_root / "workspace"
    _save_workspace_root(repo_root, str(workspace_dir))
    return workspace_dir


# -- main window -------------------------------------------------------------


class _UpdaterWindow:
    """Progress window — status label + indeterminate ttk.Progressbar.
    Runs prereq checks/self-update on a background thread; a queue.Queue is
    how it talks back, since Tk widgets aren't safe to touch from any
    thread but the one running mainloop()."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        # Nested app-repo clone — see module docstring.
        self.app_root = repo_root / APP_DIRNAME
        # data/ is the app's own git-tracked/R2-synced registry — stays
        # under app_root, force-reset along with the rest of the app on
        # every update (see ensure_up_to_date's docstring).
        self._data_dir = self.app_root / "data"
        self._interpreter: str | None = None
        self.token_store: TokenStore | None = None
        self.local_config_store: LocalConfigStore | None = None
        self.system_config_store: SystemConfigStore | None = None
        self._continue_after_id: str | None = None

        self._download_url: str | None = None

        self.root = tk.Tk()
        self.root.title("UkoreHub")
        self.root.geometry("420x180")
        self.root.resizable(False, False)
        if _ICON_PATH.exists():
            try:
                self.root.iconbitmap(str(_ICON_PATH))
            except tk.TclError:
                pass
        self.root.protocol("WM_DELETE_WINDOW", lambda: sys.exit(1))

        # First run only (see ensure_workspace_dir) — cache/ and storage/
        # are per-machine (login tokens, cloned-repo workspace) and live
        # under here rather than under app_root, so they survive every app
        # force-reset untouched; passed down to launcher.py via
        # UKOREHUB_CACHE_DIR/UKOREHUB_STORAGE_DIR in _launch (see
        # UkoreHub's own README, "Overriding cache/storage location").
        self.workspace_dir = ensure_workspace_dir(repo_root, self.root)
        self._cache_dir = self.workspace_dir / "cache"
        self._storage_dir = self.workspace_dir / "storage"

        self.status_var = tk.StringVar(value="Starting...")
        ttk.Label(self.root, textvariable=self.status_var, padding=16, wraplength=380).pack(fill="x")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=16)
        self.progress.start(12)

        self.switch_account_button = ttk.Button(
            self.root, text="Not you? Switch Account", command=self._on_switch_account_clicked
        )
        self.login_button = ttk.Button(self.root, text="Login with GitHub", command=self._start_login_flow)
        self.download_button = ttk.Button(self.root, text="Download", command=self._on_download_clicked)
        self.exit_button = ttk.Button(self.root, text="Exit", command=lambda: sys.exit(1))

        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._worker = threading.Thread(target=self._do_prelaunch_work, daemon=True)
        self._worker.start()
        self.root.after(100, self._poll_queue)

    def _do_prelaunch_work(self) -> None:
        # git is checked first because the update step right after it
        # depends on it (git fetch/pull) — everything else, including the
        # Python check, waits until UkoreHub itself is confirmed up to date.
        self._queue.put(("status", "Checking for git..."))
        if not check_git_prerequisite():
            self._queue.put((
                "fail",
                "UkoreHub requires 'git' to be installed and available on your PATH.\n"
                "Download and install it, then restart UkoreHub.",
                GIT_DOWNLOAD_URL,
            ))
            return

        if _is_dev_checkout(self.repo_root):
            # See _is_dev_checkout's docstring — never self-update either
            # this repo or app/ here, both are this dev repo's own working
            # tree, not independent release-repo clones.
            self._queue.put(("status", "Dev mode — using local app/, skipping auto-update."))
            if not (self.app_root / "launcher.py").exists():
                self._queue.put((
                    "fail",
                    f"Dev mode: no launcher.py found under {self.app_root}.\n"
                    "Run UkoreHubLauncher.exe from this repo's own root.",
                    None,
                ))
                return
        else:
            self._queue.put(("status", "Checking for launcher updates..."))
            try:
                ensure_up_to_date(self.repo_root, LAUNCHER_REMOTE_URL, LAUNCHER_BRANCH)
            except UpdaterError as exc:
                self._queue.put((
                    "fail",
                    f"UkoreHub launcher update failed:\n{exc}\n\n"
                    "You can continue with the current version — restart to retry.",
                    None,
                ))
                return

            self._queue.put(("status", "Checking for updates..."))
            try:
                self.app_root.mkdir(parents=True, exist_ok=True)
                ensure_up_to_date(self.app_root, UKOREHUB_REMOTE_URL, UKOREHUB_BRANCH)
            except UpdaterError as exc:
                self._queue.put((
                    "fail",
                    f"UkoreHub update failed:\n{exc}\n\nYou can continue with the current version — restart to retry.",
                    None,
                ))
                return

        self._queue.put(("status", "Checking for Python..."))
        interpreter = find_python_interpreter()
        if interpreter is None:
            self._queue.put((
                "fail",
                "UkoreHub requires Python to be installed and available on your PATH.\n"
                "Download and install it, then restart UkoreHub.",
                PYTHON_DOWNLOAD_URL,
            ))
            return

        self._queue.put(("status", "Checking for git-lfs..."))
        if not check_git_lfs_prerequisite():
            # Non-fatal: some repos need it, but UkoreHub itself doesn't — keep going.
            self._queue.put(("status", "git-lfs not found — continuing without it..."))

        self._queue.put(("prelaunch_ready", interpreter))

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._queue.get_nowait()
                kind = item[0]
                if kind == "status":
                    self.status_var.set(item[1])
                elif kind == "fail":
                    self._show_error(item[1], item[2])
                    return  # stop polling — window stays open until the user closes it
                elif kind == "prelaunch_ready":
                    self._on_prelaunch_ready(item[1])
                    return  # login flow drives the window from here
                elif kind == "login_verified":
                    self._on_login_verified(item[1])
                    return
                elif kind == "login_invalid":
                    self._on_login_invalid()
                    return
                elif kind == "login_verify_skipped":
                    self._on_login_verify_skipped()
                    return
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _show_error(self, message: str, download_url: str | None = None) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.status_var.set(message)
        if download_url:
            self._download_url = download_url
            self.download_button.pack(pady=(4, 0))
        self.exit_button.pack(pady=8)

    def _on_download_clicked(self) -> None:
        if self._download_url:
            webbrowser.open(self._download_url)

    def _on_prelaunch_ready(self, interpreter: str) -> None:
        self._interpreter = interpreter
        self._data_dir.mkdir(exist_ok=True)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        # github_token.json/local_config.json live under cache/, not data/ —
        # same per-machine files launcher.py itself reads/writes (see its
        # own cache_dir comment) — so a copy of data/ alone (e.g. a manual
        # zip release, rather than a fresh git clone) never carries a
        # cached login along with it. cache/ now lives under the
        # user-chosen workspace_dir (see ensure_workspace_dir), outside
        # app_root, so this is also what keeps a login surviving every app
        # force-reset.
        self.token_store = TokenStore(self._cache_dir / "github_token.json")
        self.local_config_store = LocalConfigStore(self._cache_dir / "local_config.json")
        self.system_config_store = SystemConfigStore(self._data_dir / "system_config.json")
        self._check_login()

    def _check_login(self) -> None:
        token = self.token_store.load_token()
        if token:
            # A cached token can be stale (revoked/expired on GitHub's side
            # since the last launch) — verify it against the API before
            # trusting it, rather than just checking that a value is
            # present. Runs off the Tk thread since it's a network call;
            # result comes back through the same queue _poll_queue already
            # drains, so polling has to resume here.
            self.status_var.set("Verifying sign-in...")
            threading.Thread(target=self._verify_token, args=(token,), daemon=True).start()
            self.root.after(100, self._poll_queue)
            return
        # No cached token — wait for an explicit click rather than popping
        # the device-flow dialog (and opening a browser tab) the instant
        # this window appears. _start_login_flow is the login_button's
        # command, so this is a no-op until the user actually clicks it.
        self.progress.stop()
        self.status_var.set("Please log in to GitHub to continue.")
        self.login_button.pack(pady=(4, 0))

    def _verify_token(self, token: str) -> None:
        try:
            username = github_auth.fetch_username(token)
        except GitHubAuthError as exc:
            cause = exc.__cause__
            if isinstance(cause, urllib.error.HTTPError) and cause.code in (401, 403):
                self._queue.put(("login_invalid",))
            else:
                # Couldn't reach the API (offline/transient) rather than a
                # confirmed-bad token — don't force a re-login over that.
                self._queue.put(("login_verify_skipped",))
        else:
            self._queue.put(("login_verified", username))

    def _on_login_verified(self, username: str) -> None:
        self.local_config_store.set_github_username(username)
        self._show_signed_in(username)

    def _on_login_verify_skipped(self) -> None:
        self._show_signed_in(self.local_config_store.github_username)

    def _show_signed_in(self, username: str | None) -> None:
        self.status_var.set(f"Signed in as {username}" if username else "Signed in.")
        self.switch_account_button.pack(pady=(4, 0))
        # Brief pause (not an instant auto-continue) so "Switch Account" is
        # actually clickable on a normal fast launch, not just a flash
        # before the window closes — this is the only place a user can
        # switch/log out now that Settings' old Logout button relaunches
        # back to this same screen. after_cancel-able so
        # _on_switch_account_clicked can interrupt it if clicked in time.
        self._continue_after_id = self.root.after(1500, self._finish)

    def _on_login_invalid(self) -> None:
        # Cached token was rejected by GitHub (revoked/expired) — clear it
        # and fall back to the normal no-token path instead of launching
        # into an app that'll just show "Not Signed In" anyway.
        self.token_store.clear_token()
        self.local_config_store.set_github_username(None)
        self.local_config_store.set_github_login_at(None)
        self.progress.stop()
        self.status_var.set("Your GitHub sign-in has expired. Please log in again.")
        self.login_button.pack(pady=(4, 0))

    def _start_login_flow(self) -> None:
        self.login_button.pack_forget()
        self.switch_account_button.pack_forget()
        self.progress.pack(fill="x", padx=16)
        self.progress.start(12)
        self.status_var.set("Waiting for GitHub login...")
        dialog = _LoginDialog(self.root, client_id=self.system_config_store.github_client_id or DEFAULT_GITHUB_CLIENT_ID)
        if not dialog.wait():
            # Login is mandatory — cancelling exits the launcher entirely,
            # same as the deleted LoginOverlay's semantics.
            sys.exit(1)
        try:
            self.token_store.save_token(dialog.token)
        except TokenStoreFallbackUsed as exc:
            messagebox.showwarning("GitHub Login", str(exc))
        self.local_config_store.set_github_username(dialog.username)
        self.local_config_store.set_github_login_at(datetime.now(timezone.utc).isoformat())
        self.switch_account_button.pack(pady=(4, 0))
        self.status_var.set(f"Signed in as {dialog.username}")
        self._finish()

    def _on_switch_account_clicked(self) -> None:
        if self._continue_after_id is not None:
            self.root.after_cancel(self._continue_after_id)
            self._continue_after_id = None
        self.token_store.clear_token()
        self.local_config_store.set_github_username(None)
        self.local_config_store.set_github_login_at(None)
        self._start_login_flow()

    def _finish(self) -> None:
        self.status_var.set("Launching...")
        _launch(self.app_root, self._interpreter, self._cache_dir, self._storage_dir)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def _launch(app_root: Path, interpreter: str, cache_dir: Path, storage_dir: Path) -> None:
    launcher_path = app_root / "launcher.py"
    # Points launcher.py's per-machine cache/workspace outside app_root
    # (see UKOREHUB_CACHE_DIR/UKOREHUB_STORAGE_DIR in UkoreHub's own
    # README) so neither gets force-reset away on the next app update.
    env = os.environ.copy()
    env["UKOREHUB_CACHE_DIR"] = str(cache_dir)
    env["UKOREHUB_STORAGE_DIR"] = str(storage_dir)
    # Shared R2 cloud-sync key (see the module-level R2_* import above) —
    # only set when this build actually has one baked in, so a dev build
    # without r2_credentials.py still launches, just with cloud sync
    # disabled (app/launcher.py's _build_cloud_sync treats a missing var
    # as "not configured").
    for env_name, value in (
        ("UKOREHUB_R2_ACCOUNT_ID", R2_ACCOUNT_ID),
        ("UKOREHUB_R2_ACCESS_KEY_ID", R2_ACCESS_KEY_ID),
        ("UKOREHUB_R2_SECRET_ACCESS_KEY", R2_SECRET_ACCESS_KEY),
        ("UKOREHUB_R2_BUCKET_NAME", R2_BUCKET_NAME),
    ):
        if value:
            env[env_name] = value
    subprocess.Popen(
        [interpreter, str(launcher_path)],
        cwd=str(app_root),
        env=env,
        creationflags=_NO_WINDOW_FLAGS,
    )


def main(repo_root: Path) -> None:
    """repo_root is this launcher repo's own root (UkoreHubLauncher.exe's folder) —
    see module docstring for how the nested app/ clone gets derived and
    bootstrapped from there."""
    _UpdaterWindow(repo_root).run()
