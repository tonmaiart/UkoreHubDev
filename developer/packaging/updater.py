"""UI/logic behind UkoreHub.exe (see exe_entry.py, the PyInstaller compile
target that just calls main() here).

Handles everything that has to happen before launcher.py can even be
spawned, in this order: check that git is on PATH (required — shows a
"Download" button linking to the official installer and stops if it's
missing, no silent auto-install anymore), bring REPO_ROOT up to date with
origin/main *before* anything else that could be skipped by a stale
checkout (bootstrapping it into a real git clone first if it's a plain ZIP
extract with no .git directory), check that Python is on PATH (also
required, same Download-button treatment, used to spawn launcher.py),
check git-lfs (optional — warns and continues if missing, no
auto-install), then GitHub login — this module is now the sole place
login happens and the GitHub token gets cached (TokenStore); the old
mandatory in-app login gate (interface/login/) is gone. Finally spawns
launcher.py detached, same hand-off as before.

Uses `tkinter` (stdlib, ships with every python.org Windows install that
includes Tcl/Tk, the default) rather than PySide6: a PySide6 build of just this pre-launch stage came out to ~50MB
(Qt6Core/Qt6Gui/Qt6Widgets + the opengl32sw.dll software-rasterizer
fallback alone are ~45MB, largely unavoidable even after excluding every
unrelated Qt submodule — see git history around
`developer/packaging/build_exe.py`'s now-removed `_UNUSED_PYSIDE6_MODULES`
list), against tkinter's ~5-8MB (`tcl86t.dll`/`tk86t.dll` + script
library). The device-flow login dialog (`_LoginDialog` below) is a
tkinter `Toplevel` port of the old PySide6 version, same shape.

Import discipline: the prerequisite-check helpers and the git bootstrap/
update logic below are intentionally near-duplicates of launcher.py's and
core/self_update.py's respectively (core/git_service.py and
core/self_update.py are still actively used elsewhere and more likely to
change — keeping this pre-launch copy minimal and self-contained avoids
coupling the frozen exe to that churn). GitHub login is different: since
the in-app login UI (interface/login/) was deleted entirely, this module is
now core/github/auth.py's and core/github/token_store.py's *only*
consumer for the actual OAuth flow, so they're imported directly rather
than duplicated — both are confirmed stdlib-only (auth.py uses urllib
only; token_store.py imports keyring lazily inside try/except with a
JSON-file fallback). core/store.py (SystemConfigStore/LocalConfigStore) is
also stdlib-only (only pulls in core/paths.py and core/theme.py).
"""
from __future__ import annotations

import contextlib
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, ttk

from core.exceptions import GitHubAuthError
from core.github import auth as github_auth
from core.github.token_store import TokenStore, TokenStoreFallbackUsed
from core.store import LocalConfigStore, SystemConfigStore

UKOREHUB_REMOTE_URL = "https://github.com/tonmaiart/UkoreHub.git"
UKOREHUB_BRANCH = "main"
GIT_DOWNLOAD_URL = "https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.3/Git-2.55.0.3-64-bit.exe"
PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/pymanager/python-manager-26.3.msix"

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


def _untrack_paths_deleted_upstream(repo_root: Path, local_head: str, upstream_head: str) -> None:
    """Best-effort: `git rm --cached` every path that's tracked at
    `local_head` but no longer present at `upstream_head` — leaves the
    actual file on disk untouched, only drops it from git's index. A file
    the running app writes to directly with no commit step (e.g.
    data/projects.json before it moved to cloud sync — see
    developer/bug-history/2026-08-09-shared-data-git-pull-conflict.md) is
    always "locally modified" from git's point of view, so the moment an
    incoming pull tries to delete that same file from tracking, git
    refuses with "local changes would be overwritten by merge" instead of
    just applying the deletion. Untracking it first (independent of
    whether it's actually dirty right now) makes that conflict
    impossible, and is a no-op for a clean file pull would have deleted
    anyway."""
    deleted = _run_git(["diff", "--name-only", "--diff-filter=D", local_head, upstream_head], cwd=repo_root)
    for path in deleted.splitlines():
        if not path:
            continue
        try:
            _run_git(["rm", "--cached", "--ignore-unmatch", "-r", path], cwd=repo_root)
        except UpdaterError:
            pass  # best-effort — the retried pull below still surfaces a real remaining conflict


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
    UkoreHub.exe launched from repo_root — None for `python updater.py`/
    pytest, where nothing needs relocating and git can touch the working
    tree freely."""
    if not getattr(sys, "frozen", False):
        return None
    exe_path = repo_root / "UkoreHub.exe"
    try:
        return exe_path if Path(sys.executable).resolve() == exe_path.resolve() else None
    except OSError:
        return None


def _cleanup_stale_relocated_exe(repo_root: Path) -> None:
    """Best-effort delete of a previous run's renamed-aside exe that never
    got cleaned up (e.g. the process was killed mid-update) — safe to retry
    since by the time a new UkoreHub.exe is running, nothing else should
    still have the old one open."""
    for stale in repo_root.glob("UkoreHub.exe.old-*"):
        try:
            stale.unlink()
        except OSError:
            pass


@contextlib.contextmanager
def _relocate_self_exe(repo_root: Path):
    """Windows refuses to unlink/overwrite the .exe file that's currently
    executing (`unable to unlink old 'UkoreHub.exe': Invalid argument` from
    `git checkout`/`git pull`), but it does allow renaming it — a running
    process keeps its open file handle regardless of what the directory
    entry is called, the same trick self-updating browsers use. Move
    UkoreHub.exe out of the way before any git operation that might touch
    it, so checkout/pull can write a fresh one at that path unobstructed;
    delete the leftover on success, or put it back if the update failed so
    "continue with the current version" (see the caller's error dialog)
    stays true."""
    exe_path = _running_self_exe_path(repo_root)
    if exe_path is None:
        yield
        return
    _cleanup_stale_relocated_exe(repo_root)
    relocated = exe_path.with_name(f"UkoreHub.exe.old-{os.getpid()}")
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
        try:
            relocated.unlink()
        except OSError:
            pass


def ensure_up_to_date(
    repo_root: Path,
    remote_url: str = UKOREHUB_REMOTE_URL,
    branch: str = UKOREHUB_BRANCH,
) -> None:
    """remote_url/branch only matter for the fresh-bootstrap case (a plain
    ZIP extract with no existing branch/upstream to speak of). Once it's a
    real clone, this follows whatever branch is actually checked out and
    its own configured upstream (@{u}) — same as core/self_update.py's
    check_for_update/pull_update — rather than assuming everyone is on
    `branch`. An admin checkout intentionally sitting on `dev` must not get
    silently pulled onto `main`.

    The whole thing runs inside _relocate_self_exe: UkoreHub.exe is
    git-tracked and not gitignored (see developer/packaging/README.md), so
    both the fresh-bootstrap checkout and an ordinary fetch+pull can end up
    trying to overwrite the very exe currently running this code."""
    with _relocate_self_exe(repo_root):
        if not is_git_repo(repo_root):
            bootstrap_git_repo(repo_root, remote_url, branch)
            return
        _run_git(["fetch"], cwd=repo_root)
        local_head = _run_git(["rev-parse", "HEAD"], cwd=repo_root)
        upstream_head = _run_git(["rev-parse", "@{u}"], cwd=repo_root)
        if local_head != upstream_head:
            try:
                _run_git(["pull"], cwd=repo_root)
            except UpdaterError as exc:
                # See _untrack_paths_deleted_upstream's docstring — a file
                # the app writes to directly (no commit step) blocks the
                # merge the moment an incoming commit stops tracking it.
                # Retry exactly once after untracking whatever the incoming
                # commits actually delete; any other failure (or a repeat of
                # this one) is a real conflict worth surfacing as-is.
                if "would be overwritten by merge" not in str(exc):
                    raise
                _untrack_paths_deleted_upstream(repo_root, local_head, upstream_head)
                _run_git(["pull"], cwd=repo_root)


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


# -- main window -------------------------------------------------------------


class _UpdaterWindow:
    """Progress window — status label + indeterminate ttk.Progressbar.
    Runs prereq checks/self-update on a background thread; a queue.Queue is
    how it talks back, since Tk widgets aren't safe to touch from any
    thread but the one running mainloop()."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._data_dir = repo_root / "data"
        self._cache_dir = repo_root / "cache"
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

        self._queue.put(("status", "Checking for updates..."))
        try:
            ensure_up_to_date(self.repo_root)
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
        self._cache_dir.mkdir(exist_ok=True)
        # github_token.json/local_config.json live under cache/, not data/ —
        # same per-machine, gitignored files launcher.py itself reads/writes
        # (see its own cache_dir comment) — so a copy of data/ alone (e.g. a
        # manual zip release, rather than a fresh git clone) never carries a
        # cached login along with it.
        self.token_store = TokenStore(self._cache_dir / "github_token.json")
        self.local_config_store = LocalConfigStore(self._cache_dir / "local_config.json")
        self.system_config_store = SystemConfigStore(self._data_dir / "system_config.json")
        self._check_login()

    def _check_login(self) -> None:
        token = self.token_store.load_token()
        if token:
            username = self.local_config_store.github_username
            self.status_var.set(f"Signed in as {username}" if username else "Signed in.")
            self.switch_account_button.pack(pady=(4, 0))
            # Brief pause (not an instant auto-continue) so "Switch Account"
            # is actually clickable on a normal fast launch, not just a
            # flash before the window closes — this is the only place a
            # user can switch/log out now that Settings' old Logout button
            # relaunches back to this same screen. after_cancel-able so
            # _on_switch_account_clicked can interrupt it if clicked in time.
            self._continue_after_id = self.root.after(1500, self._finish)
            return
        # No cached token — wait for an explicit click rather than popping
        # the device-flow dialog (and opening a browser tab) the instant
        # this window appears. _start_login_flow is the login_button's
        # command, so this is a no-op until the user actually clicks it.
        self.progress.stop()
        self.status_var.set("Please log in to GitHub to continue.")
        self.login_button.pack(pady=(4, 0))

    def _start_login_flow(self) -> None:
        self.login_button.pack_forget()
        self.switch_account_button.pack_forget()
        self.progress.pack(fill="x", padx=16)
        self.progress.start(12)
        self.status_var.set("Waiting for GitHub login...")
        dialog = _LoginDialog(self.root, client_id=self.system_config_store.github_client_id)
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
        _launch(self.repo_root, self._interpreter)
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def _launch(repo_root: Path, interpreter: str) -> None:
    launcher_path = repo_root / "launcher.py"
    subprocess.Popen(
        [interpreter, str(launcher_path)],
        cwd=str(repo_root),
        creationflags=_NO_WINDOW_FLAGS,
    )


def main(repo_root: Path) -> None:
    _UpdaterWindow(repo_root).run()
