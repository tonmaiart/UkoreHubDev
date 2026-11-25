"""Agent Bridge: lets a local AI agent (jcoopy, Merdera Project's pipeline agent) drive
UkoreHub the same way an artist does, so anything it opens gets the full pipeline setup
(linked program, per-repo tool env, launch hooks) instead of a bare exe.

Off by default, per machine: Settings > Developer > Agent Bridge (stored in the
per-machine "agent_bridge" plugin_config_store, key "enabled"). While on, a QTcpServer
listens on 127.0.0.1 (random port) and writes {port, token, pid} to
<cache_dir>/agent_bridge/session.json; only a client that can read that file (same user,
same machine) can talk to it. Protocol: one JSON object per line,
{"token": ..., "cmd": ..., "args": {...}} -> {"ok": bool, "result"|"error": ...} per line.
Commands run on the UI thread (QTcpServer signals arrive there), through the same
registries the UI uses -- see COMMANDS below.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtNetwork import QHostAddress, QTcpServer
from PySide6.QtWidgets import QCheckBox, QLabel, QPlainTextEdit, QVBoxLayout, QWidget

from plugin_api import CATEGORY_DEVELOPER, NotFoundError, SettingsTabSpec

PLUGIN_ID = "agent_bridge"
# maya_launcher (cache/plugins/maya_launcher) appends this one-shot MEL after opening a scene.
MAYA_AGENT_POST_MEL_ENV = "UKORE_MAYA_AGENT_POST_MEL"

log = logging.getLogger("AgentBridge")


def _mel_quote(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _maya_agent_mel(post_mel: str, post_python_file: str) -> str:
    """The caller's work as MEL for maya_launcher's one-shot hook. maya_launcher puts it
    FIRST in Maya's -command chain (so a failing scene open/tool hook can't skip it), so
    both parts are deferred here to run once that whole chain -- scene open included -- is
    done."""
    parts = []
    if post_mel:
        parts.append(f'evalDeferred "{_mel_quote(post_mel)}";')
    if post_python_file:
        p = str(post_python_file).replace("\\", "/").replace("'", "\\'")
        py = (f"import maya.utils; maya.utils.executeDeferred(lambda: exec(open(r'{p}', "
              f"encoding='utf-8').read(), {{'__name__': '__main__'}}))")
        parts.append(f'python("{_mel_quote(py)}");')
    return " ".join(parts)


class AgentBridge(QObject):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.store = api.plugin_config_store(PLUGIN_ID, shared=False)
        self.session_path = Path(api.cache_dir) / PLUGIN_ID / "session.json"
        self.server: QTcpServer | None = None
        self.token = ""
        self.history: deque[str] = deque(maxlen=200)
        self.listeners = []  # callables(line) -- the settings page's live log
        self._buffers = {}

    # -- lifecycle ---------------------------------------------------------------------

    @property
    def enabled(self) -> bool:
        return bool(self.store.get("enabled", False))

    def set_enabled(self, value: bool) -> None:
        self.store.set("enabled", bool(value))
        self.start() if value else self.stop()

    def start(self) -> None:
        if self.server is not None:
            return
        self.server = QTcpServer(self)
        if not self.server.listen(QHostAddress.LocalHost, 0):
            self._note(f"listen failed: {self.server.errorString()}")
            self.server = None
            return
        self.server.newConnection.connect(self._on_new_connection)
        self.token = secrets.token_hex(16)
        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_path.write_text(json.dumps({
            "port": self.server.serverPort(),
            "token": self.token,
            "pid": os.getpid(),
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }), encoding="utf-8")
        self._note(f"listening on 127.0.0.1:{self.server.serverPort()}")

    def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            self.server = None
            self._note("stopped")
        try:
            self.session_path.unlink()
        except FileNotFoundError:
            pass

    # -- transport ---------------------------------------------------------------------

    def _on_new_connection(self) -> None:
        while self.server is not None and self.server.hasPendingConnections():
            sock = self.server.nextPendingConnection()
            self._buffers[sock] = b""
            sock.readyRead.connect(lambda s=sock: self._on_ready_read(s))
            sock.disconnected.connect(lambda s=sock: self._on_disconnected(s))

    def _on_disconnected(self, sock) -> None:
        self._buffers.pop(sock, None)
        sock.deleteLater()

    def _on_ready_read(self, sock) -> None:
        self._buffers[sock] = self._buffers.get(sock, b"") + bytes(sock.readAll())
        while b"\n" in self._buffers[sock]:
            line, self._buffers[sock] = self._buffers[sock].split(b"\n", 1)
            if line.strip():
                reply = self._handle(line)
                sock.write((json.dumps(reply, default=str) + "\n").encode("utf-8"))
                sock.flush()

    def _handle(self, raw: bytes) -> dict:
        try:
            request = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            return {"ok": False, "error": f"bad json: {exc}"}
        if not secrets.compare_digest(str(request.get("token", "")), self.token):
            self._note("rejected request with a wrong token")
            return {"ok": False, "error": "bad token"}
        cmd = request.get("cmd", "")
        args = request.get("args") or {}
        handler = COMMANDS.get(cmd)
        if handler is None:
            return {"ok": False, "error": f"unknown cmd '{cmd}'", "commands": sorted(COMMANDS)}
        self._note(f"{cmd} {json.dumps(args, default=str)[:300]}")
        try:
            return {"ok": True, "result": handler(self, **args)}
        except Exception as exc:  # report every failure back to the agent, never crash the UI
            log.exception("command %s failed", cmd)
            self._note(f"{cmd} failed: {exc}")
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    def _note(self, text: str) -> None:
        line = f"{time.strftime('%H:%M:%S')}  {text}"
        self.history.append(line)
        log.info(text)
        for listener in list(self.listeners):
            listener(line)

    # -- helpers -----------------------------------------------------------------------

    def active_project(self):
        project_id = self.api.local_config.active_project_id
        if project_id is None:
            raise RuntimeError("no active project in UkoreHub")
        return self.api.metadata.get_project(project_id)

    def repo_path(self, repo) -> Path:
        return Path(self.api.local_config.workspace_root) / repo.local_path

    def find_repo(self, key: str | None = None, path: str | None = None):
        """A repo of the active project, by id / name / local_path, or the one whose folder
        contains path (deepest match)."""
        repos = list(self.active_project().repos)
        if key:
            for repo in repos:
                if key in (repo.id, getattr(repo, "name", None), repo.local_path):
                    return repo
            raise NotFoundError(f"no repo '{key}' in the active project")
        if path:
            target = Path(path).resolve()
            matches = [r for r in repos if target.is_relative_to(self.repo_path(r).resolve())]
            if matches:
                return max(matches, key=lambda r: len(str(self.repo_path(r))))
            raise NotFoundError(f"'{path}' is not inside any repo of the active project")
        raise ValueError("give repo or path")

    def with_maya_post_mel(self, mel: str, fn):
        """Run fn with maya_launcher's one-shot post-open MEL set, then clear it."""
        if mel:
            os.environ[MAYA_AGENT_POST_MEL_ENV] = mel
        try:
            return fn()
        finally:
            os.environ.pop(MAYA_AGENT_POST_MEL_ENV, None)


# -- commands --------------------------------------------------------------------------


def cmd_ping(bridge: AgentBridge) -> dict:
    cfg = bridge.api.local_config
    return {
        "pid": os.getpid(),
        "app_root": str(bridge.api.app_root),
        "workspace_root": str(cfg.workspace_root),
        "active_project_id": cfg.active_project_id,
        "active_repo_id": getattr(cfg, "active_repo_id", None),
        "plugins": sorted(p.manifest.id for p in bridge.api.plugin_catalog),
    }


def cmd_describe(bridge: AgentBridge) -> dict:
    """Public attribute names of the services an agent can drive -- for discovering the
    API without reading UkoreHub's closed source."""
    def names(obj):
        return sorted(n for n in dir(obj) if not n.startswith("_"))
    return {
        "metadata": names(bridge.api.metadata),
        "local_config": names(bridge.api.local_config),
        "file_opener_registry": names(bridge.api.file_opener_registry),
        "program_launch_registry": names(bridge.api.program_launch_registry),
    }


def cmd_list_repos(bridge: AgentBridge) -> list:
    out = []
    for repo in bridge.active_project().repos:
        out.append({
            "id": repo.id,
            "name": getattr(repo, "name", None),
            "local_path": repo.local_path,
            "path": str(bridge.repo_path(repo)),
            "exists": bridge.repo_path(repo).is_dir(),
            "required_plugin_ids": list(getattr(repo, "required_plugin_ids", []) or []),
        })
    return out


def cmd_open_file(bridge: AgentBridge, path: str, repo: str | None = None,
                  post_mel: str = "", post_python_file: str = "") -> dict:
    """Open a file with whatever plugin claims its extension (e.g. .ma/.mb -> maya_launcher:
    linked Maya, repo tool env, launch hooks, setProject). post_mel / post_python_file run
    in that program after the file opens (Maya only, via maya_launcher)."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(path)
    target_repo = bridge.find_repo(repo, path=None if repo else path)
    spec = bridge.api.file_opener_registry.find_opener(file_path)
    if spec is None:
        raise NotFoundError(f"no plugin opens '{file_path.suffix}' files")
    opener = getattr(spec, "opener", None) or getattr(spec, "open", None) or spec
    mel = _maya_agent_mel(post_mel, post_python_file)
    handled = bridge.with_maya_post_mel(mel, lambda: opener(file_path, target_repo))
    return {"handled": bool(handled), "repo": target_repo.id, "opener": getattr(spec, "plugin_id", None)}


def cmd_launch_program(bridge: AgentBridge, program: str, repo: str,
                       post_mel: str = "", post_python_file: str = "") -> dict:
    """Launch a Program (by name, e.g. "Maya") for a repo through its registered launcher."""
    target_repo = bridge.find_repo(repo)
    project = bridge.active_project()
    match = None
    for candidate in bridge.api.metadata.list_programs(project.id):
        if candidate.name.lower() == program.lower() or candidate.id == program:
            match = candidate
            break
    if match is None:
        raise NotFoundError(f"no program '{program}' in the active project")
    found = bridge.api.program_launch_registry.find_launcher(match)
    if found is None:
        raise NotFoundError(f"no launcher registered for '{match.name}'")
    launch = getattr(found, "launch", found)  # find_launcher() returns the launch callable itself
    mel = _maya_agent_mel(post_mel, post_python_file)
    handled = bridge.with_maya_post_mel(mel, lambda: launch(target_repo))
    return {"handled": bool(handled), "repo": target_repo.id, "program": match.name}


def cmd_list_programs(bridge: AgentBridge) -> list:
    return [{"id": p.id, "name": p.name} for p in bridge.api.metadata.list_programs(bridge.active_project().id)]


def cmd_history(bridge: AgentBridge, limit: int = 50) -> list:
    return list(bridge.history)[-limit:]


def cmd_list_file_actions(bridge: AgentBridge) -> list:
    return [{"key": s.key, "label": s.label} for s in bridge.api.file_context_action_registry.ordered()]


def cmd_file_action(bridge: AgentBridge, key: str, paths) -> dict:
    """Run a plugin's registered file context action by key, skipping its match() --
    the only cross-plugin callable a core plugin can reach, so a plugin exposes agent
    work (e.g. MayaPublisher's headless batch) as an action whose match() hides it
    from Explorer's menu."""
    specs = {s.key: s for s in bridge.api.file_context_action_registry.ordered()}
    spec = specs.get(key)
    if spec is None:
        raise NotFoundError(f"no file action '{key}' (have: {', '.join(sorted(specs))})")
    path_list = [Path(p) for p in ([paths] if isinstance(paths, str) else paths)]
    spec.run(path_list)
    return {"key": key, "paths": [str(p) for p in path_list]}


COMMANDS = {
    "ping": cmd_ping,
    "describe": cmd_describe,
    "list_repos": cmd_list_repos,
    "open_file": cmd_open_file,
    "launch_program": cmd_launch_program,
    "list_programs": cmd_list_programs,
    "history": cmd_history,
    "list_file_actions": cmd_list_file_actions,
    "file_action": cmd_file_action,
}


# -- settings tab ----------------------------------------------------------------------


class AgentBridgeSettingsPage(QWidget):
    def __init__(self, bridge: AgentBridge):
        super().__init__()
        self.bridge = bridge
        layout = QVBoxLayout(self)
        self.checkbox = QCheckBox("Allow a local AI agent (jcoopy) to control UkoreHub on this machine")
        self.checkbox.setChecked(bridge.enabled)
        self.checkbox.toggled.connect(self._on_toggled)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.checkbox)
        layout.addWidget(self.status)
        layout.addWidget(QLabel("Recent commands:"))
        layout.addWidget(self.log_view, 1)
        bridge.listeners.append(self._append)
        self.refresh()

    def _on_toggled(self, value: bool) -> None:
        self.bridge.set_enabled(value)
        self.refresh()

    def _append(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def refresh(self) -> None:
        if self.bridge.server is not None:
            self.status.setText(
                f"Listening on 127.0.0.1:{self.bridge.server.serverPort()} — session file: "
                f"{self.bridge.session_path}")
        else:
            self.status.setText("Off. Nothing outside UkoreHub can control it.")
        self.log_view.setPlainText("\n".join(self.bridge.history))


def register(api) -> None:
    bridge = AgentBridge(api)
    api.on_app_start(lambda ctx: bridge.start() if bridge.enabled else None)
    api.on_app_close(lambda ctx: bridge.stop())
    api.register_settings_tab(
        SettingsTabSpec(
            key=PLUGIN_ID,
            label="Agent Bridge",
            order=900,
            page_factory=lambda: AgentBridgeSettingsPage(bridge),
            on_activated=lambda page: page.refresh(),
            category=CATEGORY_DEVELOPER,
        )
    )
