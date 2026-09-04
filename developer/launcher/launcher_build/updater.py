"""UI/logic behind UkoreHubLauncher.exe (see exe_entry.py, the PyInstaller compile
target that just calls main() here).

This repo (UkoreHubLauncher) is deliberately separate from the app repo
(UkoreHub, a.k.a. "UkoreHubRelease") artists actually run — see this
repo's README. `UkoreHubLauncher.exe` lives and self-updates here;
`portal/` (its own separate repo, UkoreHubPortal) is a nested clone this
module bootstraps/updates independently, the same way it used to manage a
nested `app/` clone directly. Splitting the exe from what it spawns means
an ordinary release can never again try to overwrite the exe file that's
busy executing this very code (see UkoreHubDev's `ukorehub-launcher` skill
for the bug this eliminates for the frequent case) — only a rare
launcher-repo release (rebranding the icon, changing this file) still
needs the `_relocate_self_exe` rename-aside trick below.

Handles only what has to happen before this exe can hand off to something
that knows how to run Python: check that git is on PATH (required — shows
a "Download" button linking to the official installer and stops if it's
missing, no silent auto-install anymore), self-update this launcher repo
(rare — bootstrapping it into a real git clone first if it's a plain ZIP
extract with no .git directory), then bootstrap/update the nested
`portal/` clone the same way, check that Python is on PATH (also
required, same Download-button treatment, used to spawn portal/main.py),
install/update every package portal/requirements.txt pins via pip
(required — portal/main.py is spawned detached with no console by
default, so a missing dependency there fails silently otherwise). Finally
spawns portal/main.py detached. Everything past that point — the
workspace-location prompt, updating app/, installing app/'s own
dependencies, git-lfs check, GitHub login — is Portal's job now, not this
exe's; see portal/main.py's own docstring.

Dev mode: when this exe is run from inside the merged UkoreHubDev dev repo
instead of a real artist install (detected by `_is_dev_checkout` — a
`developer/` folder next to the exe, which no release checkout ever has),
both self-update steps above are skipped entirely and `portal/`/`app/` are
used as-is — see `_is_dev_checkout`/`_do_prelaunch_work`. This is what
lets you double-click the exe here to exercise the real pre-launch UX
(prereq checks) against your local `portal/`/`app/` edits without it
hard-resetting either working tree against a release remote.

Uses `tkinter` (stdlib, ships with every python.org Windows install that
includes Tcl/Tk, the default) rather than PySide6: a PySide6 build of just
this pre-launch stage came out to ~50MB (Qt6Core/Qt6Gui/Qt6Widgets + the
opengl32sw.dll software-rasterizer fallback alone are ~45MB, largely
unavoidable even after excluding every unrelated Qt submodule — see git
history around `build_exe.py`'s now-removed `_UNUSED_PYSIDE6_MODULES`
list), against tkinter's ~5-8MB (`tcl86t.dll`/`tk86t.dll` + script
library). Portal itself already depends on PySide6, so this tradeoff only
applies to this thin exe stage.

Import discipline: the prerequisite-check helpers and the git bootstrap/
update logic below are near-duplicates of portal/git_update.py's own
(kept minimal and self-contained so this repo never needs the portal repo
cloned locally just to build) — a change to one's git-update behavior
needs a matching update to the other if it should apply to both. This
repo's own `core/` (vendored GitHub-login/config-store copies) is no
longer used by this file now that login lives in Portal — left in place
rather than deleted, since nothing else in this repo imports it either;
safe to remove in a follow-up cleanup.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import ttk

# The shared Cloudflare R2 key for cloud sync (app/core/vcs/cloud_sync.py) —
# baked into this exe at build time via a gitignored sibling module (see
# r2_credentials.example.py's docstring for the "copy, fill in, rebuild"
# steps), never committed here or read from any JSON store. Every value is
# None on a checkout that hasn't created r2_credentials.py yet (e.g. a
# fresh dev machine) — _launch() below only sets the UKOREHUB_R2_* env vars
# when they're actually present, so app/launcher.py's own _build_cloud_sync
# falls back to local-only, same as "not configured" today. Portal forwards
# these through unchanged to app/launcher.py — see portal/main.py.
try:
    from r2_credentials import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME
except ImportError:
    R2_ACCOUNT_ID = R2_ACCESS_KEY_ID = R2_SECRET_ACCESS_KEY = R2_BUCKET_NAME = None

# The Portal repo (what `portal/` clones/updates) — Portal in turn manages
# its own nested `app/` clone (see portal/main.py), the way this exe used
# to manage `app/` directly.
PORTAL_REMOTE_URL = "https://github.com/tonmaiart/UkoreHubPortal.git"
PORTAL_BRANCH = "main"
# This launcher repo itself — what `repo_root` (UkoreHubLauncher.exe's own folder)
# self-updates from. Rare: only changes on an icon rebrand or an edit to
# this file/exe_entry.py/build_exe.py.
LAUNCHER_REMOTE_URL = "https://github.com/tonmaiart/UkoreHubLauncher.git"
LAUNCHER_BRANCH = "main"
# Name of the nested portal clone inside repo_root — gitignored by this repo
# (see .gitignore) since it's an independent git working tree, not part of
# this repo's own tracked files.
PORTAL_DIRNAME = "portal"
GIT_DOWNLOAD_URL = "https://git-scm.com/install/windows"
PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/pymanager/python-manager-26.3.msix"

_NO_WINDOW_FLAGS = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_ICON_PATH = Path(__file__).resolve().parent / "icon.ico"


class UpdaterError(Exception):
    pass


# -- prerequisite checks (presence only — no auto-install; see the
# "Download" button in _UpdaterWindow for what happens when one is missing)
# (near-duplicate of app/launcher.py's) --


def check_git_prerequisite() -> bool:
    return shutil.which("git") is not None


def find_python_interpreter() -> str | None:
    return shutil.which("pythonw") or shutil.which("python")


def find_pip_interpreter() -> str | None:
    """Prefers a real console python.exe over pythonw.exe for the pip
    subprocess below — the opposite order from find_python_interpreter,
    which prefers pythonw so portal/main.py itself doesn't flash a
    console. pythonw's stdout/stderr aren't real console streams, which
    can trip up pip's own output handling even when captured via a pipe."""
    return shutil.which("python") or shutil.which("pythonw")


# -- git bootstrap/update (near-duplicate of portal/git_update.py's) -------


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


def _requirements_marker_path(requirements_path: Path) -> Path:
    return requirements_path.with_name(requirements_path.name + ".installed-hash")


def _requirements_up_to_date(requirements_path: Path) -> bool:
    """True when the last successful ensure_dependencies_installed run
    already covered this exact requirements.txt content — lets the caller
    skip the pip subprocess entirely, which costs a second or more even
    when its own dependency resolver finds nothing to do. The marker lives
    next to requirements.txt as a plain untracked file, so it's swept by
    _clean_untracked whenever a real update actually lands (forcing a
    reinstall then) but survives an ordinary no-update launch."""
    marker_path = _requirements_marker_path(requirements_path)
    if not marker_path.exists():
        return False
    try:
        digest = hashlib.sha256(requirements_path.read_bytes()).hexdigest()
        return marker_path.read_text(encoding="utf-8").strip() == digest
    except OSError:
        return False


def _mark_requirements_installed(requirements_path: Path) -> None:
    try:
        digest = hashlib.sha256(requirements_path.read_bytes()).hexdigest()
        _requirements_marker_path(requirements_path).write_text(digest, encoding="utf-8")
    except OSError:
        pass


def ensure_dependencies_installed(portal_root: Path, interpreter: str) -> None:
    """Installs/updates every package portal/requirements.txt pins, using a
    console-capable interpreter (see find_pip_interpreter) rather than
    necessarily the pythonw one portal/main.py itself gets spawned with.

    Skips the pip subprocess when requirements.txt's content hash matches
    the marker left by the last successful install (see
    _requirements_up_to_date) — the common case on every ordinary launch.
    A release that adds/bumps a dependency changes requirements.txt's
    bytes, which changes the hash, which forces a real reinstall: this
    never hides a genuine new dependency, it only skips the redundant
    no-op pip run. portal/main.py is spawned detached with no console by
    default (see _launch), so a package a release just added that isn't
    yet installed on this machine would otherwise fail as a silent
    ModuleNotFoundError — no window, no visible error, just "the app
    doesn't open" — which is why this still runs at all rather than being
    removed outright."""
    requirements_path = portal_root / "requirements.txt"
    if not requirements_path.exists():
        return
    if _requirements_up_to_date(requirements_path):
        return
    pip_interpreter = find_pip_interpreter() or interpreter
    result = subprocess.run(
        [
            pip_interpreter,
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path),
            "--disable-pip-version-check",
            "--quiet",
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        env=_non_interactive_env(),
        creationflags=_NO_WINDOW_FLAGS,
    )
    if result.returncode != 0:
        raise UpdaterError(result.stderr.strip() or result.stdout.strip() or "pip install failed")
    _mark_requirements_installed(requirements_path)


def is_git_repo(repo_root: Path) -> bool:
    return (repo_root / ".git").exists()


def bootstrap_git_repo(repo_root: Path, remote_url: str, branch: str) -> None:
    """Turns a plain folder (e.g. a GitHub "Download ZIP" extract, which has
    no .git directory at all) into a real git working tree tracking
    remote_url/branch, in place — so every later run can use ordinary git
    fetch/pull from then on."""
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
    "/portal/",
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
    remote_url: str = PORTAL_REMOTE_URL,
    branch: str = PORTAL_BRANCH,
) -> None:
    """remote_url/branch only matter for the fresh-bootstrap case (a plain
    ZIP extract with no existing branch/upstream to speak of). Once it's a
    real clone, this follows whatever branch is actually checked out and
    its own configured upstream (@{u}) rather than assuming everyone is on
    `branch`. An admin checkout intentionally sitting on `dev` must not get
    silently pulled onto `main`.

    Forces the working tree to exactly match upstream (fetch + clean -fd +
    reset --hard) instead of `git pull` (a merge, which git refuses the
    moment anything local — a modified tracked file, or an untracked file
    sitting where an incoming commit wants to add one — is in the way).
    There is nothing in this working tree worth a merge conflict over:
    per-machine files (cache/, storage/) live outside it entirely (see
    _UpdaterWindow). The clean step (_clean_untracked) only ever removes
    files this repo genuinely doesn't want lying around — never the
    per-machine/in-flight ones above.

    Only ever called against this launcher repo's own root now (which has
    UkoreHubLauncher.exe git-tracked in it, so _relocate_self_exe actually
    does something) and against the nested `portal/` directory (where
    _relocate_self_exe is a no-op, since UkoreHubLauncher.exe was never
    part of that working tree) — safe to reuse for both without any
    special-casing."""
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
    developer/release_launcher.ps1 / developer/release_portal.ps1 before
    anything is published), so its presence next to the exe is the signal
    to use. In that case repo_root is this dev repo's own git working tree
    (not the UkoreHubLauncher release repo) and portal_root (portal/) is a
    plain top-level subfolder of it, not an independent clone of the
    UkoreHubPortal release repo — ensure_up_to_date must never run against
    either (see _do_prelaunch_work)."""
    return (repo_root / "developer").exists()


# -- main window -------------------------------------------------------------


class _UpdaterWindow:
    """Progress window — status label + indeterminate ttk.Progressbar.
    Runs prereq checks/self-update on a background thread; a queue.Queue is
    how it talks back, since Tk widgets aren't safe to touch from any
    thread but the one running mainloop()."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        # Nested portal-repo clone — see module docstring.
        self.portal_root = repo_root / PORTAL_DIRNAME
        self._interpreter: str | None = None

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

        self.status_var = tk.StringVar(value="Starting...")
        ttk.Label(self.root, textvariable=self.status_var, padding=16, wraplength=380).pack(fill="x")

        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=16)
        self.progress.start(12)

        self.download_button = ttk.Button(self.root, text="Download", command=self._on_download_clicked)
        self.exit_button = ttk.Button(self.root, text="Exit", command=lambda: sys.exit(1))

        self._queue: "queue.Queue[tuple]" = queue.Queue()
        self._worker = threading.Thread(target=self._do_prelaunch_work, daemon=True)
        self._worker.start()
        self.root.after(100, self._poll_queue)

    def _do_prelaunch_work(self) -> None:
        # git is checked first because the update step right after it
        # depends on it (git fetch/pull) — everything else, including the
        # Python check, waits until Portal itself is confirmed up to date.
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
            # this repo or portal/ here, both are this dev repo's own
            # working tree, not independent release-repo clones.
            self._queue.put(("status", "Dev mode — using local portal/, skipping auto-update."))
            if not (self.portal_root / "main.py").exists():
                self._queue.put((
                    "fail",
                    f"Dev mode: no portal/main.py found under {self.repo_root}.\n"
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
                self.portal_root.mkdir(parents=True, exist_ok=True)
                ensure_up_to_date(self.portal_root, PORTAL_REMOTE_URL, PORTAL_BRANCH)
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

        self._queue.put(("status", "Installing required Python packages..."))
        try:
            ensure_dependencies_installed(self.portal_root, interpreter)
        except UpdaterError as exc:
            self._queue.put((
                "fail",
                f"Failed to install required Python packages:\n{exc}\n\n"
                "Check your internet connection and restart UkoreHub.",
                None,
            ))
            return

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
        self.status_var.set("Launching...")
        _launch(self.portal_root, self._interpreter)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def _launch(portal_root: Path, interpreter: str) -> None:
    # Spawns portal/main.py — the new hand-off point, which owns the
    # workspace-location prompt (cache/storage/data dirs), updating app/,
    # installing app/'s dependencies, git-lfs check, GitHub login, and
    # finally spawning app/launcher.py itself (see that file's own
    # docstring). Portal resolves UKOREHUB_CACHE_DIR/UKOREHUB_STORAGE_DIR/
    # UKOREHUB_DATA_DIR itself now rather than inheriting them from here.
    portal_path = portal_root / "main.py"
    env = os.environ.copy()
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
        [interpreter, str(portal_path)],
        cwd=str(portal_root),
        env=env,
        creationflags=_NO_WINDOW_FLAGS,
    )


def main(repo_root: Path) -> None:
    """repo_root is this launcher repo's own root (UkoreHubLauncher.exe's folder) —
    see module docstring for how the nested portal/ clone gets derived and
    bootstrapped from there."""
    _UpdaterWindow(repo_root).run()
