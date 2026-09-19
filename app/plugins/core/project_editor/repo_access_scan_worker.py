from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from plugin_api import GitHubAuthError, GitService, get_repo_permissions


class RepoAccessScanWorker(QThread):
    """Background GitHub push-permission check for every repo in the table
    (tableWidget_Repo's Access column) — a local duplicate of
    repo_status_scan_worker.py's QThread-wraps-a-callable shape rather than
    a shared base class, same don't-import-a-sibling-plugin's-source
    boundary this plugin follows elsewhere. Unlike that worker this one
    doesn't need the repo to be cloned at all — it's a pure GitHub API call,
    so every repo in the project is checked regardless of local clone
    state. Only meaningful for a github.com remote with a token available —
    anything else reports "unknown" (access_unknown) rather than guessing,
    same ambiguity get_repo_permissions already documents for a repo it
    can't see at all."""

    access_ready = Signal(str, bool)  # repo_id, has_push
    access_unknown = Signal(str)  # repo_id
    scan_finished = Signal()

    def __init__(
        self,
        *,
        git_service: GitService,
        targets: list[tuple[str, str]],  # (repo_id, git_url)
        token: str | None,
        parent=None,
    ):
        super().__init__(parent)
        self._git_service = git_service
        self._targets = targets
        self._token = token

    def run(self) -> None:
        for repo_id, git_url in self._targets:
            owner_repo = self._git_service.parse_github_owner_repo(git_url) if git_url else None
            if owner_repo is None or not self._token:
                self.access_unknown.emit(repo_id)
                continue
            try:
                permissions = get_repo_permissions(owner_repo[0], owner_repo[1], self._token)
            except GitHubAuthError:
                self.access_unknown.emit(repo_id)
                continue
            self.access_ready.emit(repo_id, bool(permissions and permissions.get("push")))
        self.scan_finished.emit()
