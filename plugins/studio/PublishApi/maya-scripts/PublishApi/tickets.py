"""Per-ticket configuration for PublishApi-based Publisher tools
(ModelPublisher, RigPublisher, AnimationPublisher) — replaces the old
single "repo_publish_target" choice (one Publish Path per tool per repo,
picked in a UkoreHub-side Repo Studio Setting tab) with user-managed
**tickets**, created/renamed/deleted entirely from each tool's own Maya
window (see ticket_manager_dialog.py). Each ticket has its own display
`name`, its own immutable on-disk `folder_name`, its own `publish_target`
(a pipeline connection ref, same shape the old single choice used), and
its own folder of validation scripts that must all pass before
`function.py`'s `publish()` is allowed to run.

Storage: data/plugins/studio/<tool_id>.json, key "tickets", a dict keyed
by "<project_id>:<repo_id>" (the *active* repo doing the publishing — same
key shape the old "repo_publish_target" used, see _migrate_legacy_target
below for how an existing choice under that old key is carried forward).
Every function here follows repo_paths.py's own "construct the store
straight off disk" convention — Maya's Python has no PluginAPI instance to
call plugin_config_store() through.

Validation scripts are real .py files living in a **fixed, repo-committed
folder** — <active repo's own local clone>/PublishValidation/<tool_id>/ —
authored/edited entirely outside this tool (a text editor, committed to
the repo like any other pipeline code, shared to the whole team via that
repo's own git history) rather than created through PublishApi. A ticket
just stores which of the scripts already sitting in that folder apply to
it (`ticket["script_names"]`, a list of filenames) — "attach"/"detach",
not "create"/"delete". Loading borrows the "folder of individually loaded
scripts" convention from tmlib.core.QuickData
(plugins/studio/MayaToolkit/maya-scripts/tmlib/core/QuickData.py, used by
the PythonReader toolkit, formerly "QuickScript") — same
importlib.util.spec_from_file_location/exec_module mechanism as its
run_script_file(), except we call validate() instead of run() and collect
the bool results instead of discarding them."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from PublishApi import repo_paths


def _tool_store(tool_id: str):
    from core.extensibility.config_store import PluginConfigStore

    root = repo_paths.find_ukorehub_root()
    return PluginConfigStore(root / "data" / "plugins" / "studio" / f"{tool_id}.json")


def _active_key() -> tuple[str, str, str] | None:
    """("<project_id>:<repo_id>", project_id, repo_id) for whichever repo
    is currently active in UkoreHub, or None if there isn't one."""
    project, repo, _ = repo_paths.get_active_repo()
    if project is None:
        return None
    return f"{project.id}:{repo.id}", project.id, repo.id


def _migrate_legacy_target(store, key: str) -> list[dict]:
    """One-time upgrade: if this repo already had an old-style single
    "repo_publish_target" choice and no tickets yet, carry it forward as a
    "Main" ticket instead of silently losing it (this is exactly the
    RigTeam -> PublishToUnity choice made earlier via the now-removed
    UkoreHub Repository Setting tab)."""
    import uuid

    legacy = store.get("repo_publish_target", {}).get(key)
    if legacy is None:
        return []
    return [
        {
            "id": uuid.uuid4().hex,
            "name": "Main",
            "folder_name": "Main",
            "publish_target": {
                "project_id": legacy.get("project_id"),
                "repo_id": legacy.get("repo_id"),
                "custom_path_id": legacy.get("custom_path_id"),
            },
            "script_names": [],
        }
    ]


def list_tickets(tool_id: str) -> list[dict]:
    """The active repo's tickets for `tool_id`, running the one-time
    legacy migration if this repo has none yet. [] if there's no active
    repo."""
    key_info = _active_key()
    if key_info is None:
        return []
    key, _project_id, _repo_id = key_info

    store = _tool_store(tool_id)
    all_tickets = store.get("tickets", {})
    tickets = all_tickets.get(key)

    if tickets is None:
        tickets = _migrate_legacy_target(store, key)
        all_tickets[key] = tickets
        store.set("tickets", all_tickets)

    return tickets


def _save_tickets(tool_id: str, key: str, tickets: list[dict]) -> None:
    store = _tool_store(tool_id)
    all_tickets = store.get("tickets", {})
    all_tickets[key] = tickets
    store.set("tickets", all_tickets)


def create_ticket(tool_id: str, name: str, folder_name: str) -> dict:
    """Raises ValueError if `folder_name` collides with an existing
    ticket's folder for this repo — two tickets silently sharing one
    version-history folder is a footgun worth blocking outright, not
    something to quietly allow."""
    import uuid

    key_info = _active_key()
    if key_info is None:
        raise RuntimeError("No active repo selected in UkoreHub.")
    key, _project_id, _repo_id = key_info

    existing = list_tickets(tool_id)
    if any(t["folder_name"] == folder_name for t in existing):
        raise ValueError(f"A ticket already publishes into folder '{folder_name}' for this repo.")

    ticket = {
        "id": uuid.uuid4().hex,
        "name": name,
        "folder_name": folder_name,
        "publish_target": None,
        "script_names": [],
    }
    existing.append(ticket)
    _save_tickets(tool_id, key, existing)
    return ticket


def _update_ticket(tool_id: str, ticket_id: str, mutate) -> None:
    key_info = _active_key()
    if key_info is None:
        return
    key, _project_id, _repo_id = key_info
    tickets = list_tickets(tool_id)
    for ticket in tickets:
        if ticket["id"] == ticket_id:
            mutate(ticket)
            break
    _save_tickets(tool_id, key, tickets)


def rename_ticket(tool_id: str, ticket_id: str, new_name: str) -> None:
    """Only `name` changes — `folder_name` is immutable after creation, so
    renaming a ticket never moves/breaks its already-published versions."""
    _update_ticket(tool_id, ticket_id, lambda t: t.update(name=new_name))


def set_ticket_publish_target(tool_id: str, ticket_id: str, ref: dict | None) -> None:
    _update_ticket(tool_id, ticket_id, lambda t: t.update(publish_target=ref))


def set_ticket_export_type(tool_id: str, ticket_id: str, export_type: str) -> None:
    """Only meaningful for animation_publisher tickets ("playblast" or
    "unreal") — Rig/Model tickets never get this key."""
    _update_ticket(tool_id, ticket_id, lambda t: t.update(export_type=export_type))


def delete_ticket(tool_id: str, ticket_id: str) -> None:
    """Removes the ticket's JSON entry only — does not delete its scripts
    folder or any already-published output. Deleting a folder the user
    might not realize still matters (old versions, scripts they forgot
    about) is exactly the kind of silent destructive action this codebase
    avoids elsewhere."""
    key_info = _active_key()
    if key_info is None:
        return
    key, _project_id, _repo_id = key_info
    tickets = [t for t in list_tickets(tool_id) if t["id"] != ticket_id]
    _save_tickets(tool_id, key, tickets)


def get_publish_root_for_ticket(tool_id: str, ticket: dict) -> str:
    """The publish destination root for this specific ticket — its own
    chosen Publish Path, resolved to <target repo's cloned path>/<its
    chosen CustomPath's own relative path>. Same RuntimeError-with-
    human-message contract the old per-tool get_publish_root(tool_id) had,
    just resolved from ticket["publish_target"] instead — no "auto-pick
    the repo's only connection" fallback, since each ticket now makes its
    own explicit choice."""
    project, _repo, _ = repo_paths.get_active_repo()
    if project is None:
        raise RuntimeError(
            "No active repo selected in UkoreHub. Open UkoreHub, pick a project/repo, then try again."
        )

    ref = ticket.get("publish_target")
    if ref is None:
        raise RuntimeError(
            f"Ticket '{ticket['name']}' has no Publish Path set yet. "
            "Pick one under Manage Tickets... in this tool's window."
        )

    resolved = repo_paths.resolve_ref(ref)
    if resolved is None:
        raise RuntimeError(f"Ticket '{ticket['name']}'s chosen Publish Path's target repo no longer exists.")
    _target_project, target_repo, target_repo_path = resolved

    if not target_repo_path.is_dir():
        raise RuntimeError(
            f"Publish Path target repo '{target_repo.name}' hasn't been cloned yet — clone it in UkoreHub first."
        )

    custom_path = repo_paths.get_custom_path(ref["project_id"], ref["repo_id"], ref.get("custom_path_id"))
    if custom_path is None:
        raise RuntimeError(
            f"'{target_repo.name}'s declared Custom Path for ticket '{ticket['name']}' no longer exists — "
            "re-pick a Publish Path for this ticket under Manage Tickets..."
        )

    # See bug-history/2026-07-20-playblast-custom-path-leading-slash.md /
    # bug-history/2026-08-03-publishapi-custom-path-leading-slash.md —
    # custom_path["path"] is raw user input; a leading separator would
    # anchor this join to the current drive root instead of target_repo_path.
    return str(target_repo_path / custom_path["path"].lstrip("/\\"))


def validation_scripts_dir(tool_id: str) -> Path:
    """The fixed, repo-committed folder validation scripts for `tool_id`
    live in — <active repo's own local clone>/PublishValidation/<tool_id>/
    — created on first use if it doesn't exist yet. Unlike ticket
    metadata, this is NOT under UkoreHub's own data/: it's part of the
    active repo's own checked-out pipeline code, so it's naturally
    shared/versioned via that repo's own git history (a TD commits a
    script here like any other pipeline file) instead of UkoreHub's
    install. Per-tool (not shared across Rig/Model/Animation) since a
    Rig-scene check and a Model-scene check are rarely the same script."""
    _project, _repo, repo_path = repo_paths.get_active_repo()
    if repo_path is None:
        raise RuntimeError("No active repo selected in UkoreHub.")
    folder = repo_path / "PublishValidation" / tool_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_available_scripts(tool_id: str) -> list[Path]:
    """Every .py file currently sitting in this repo's fixed validation-
    script folder for `tool_id` — authored/edited entirely outside this
    tool (a text editor, committed to the repo), not created through
    PublishApi. See ticket_manager_dialog.py's "Open Script Folder..."
    button for jumping straight to this folder."""
    folder = validation_scripts_dir(tool_id)
    return sorted(p for p in folder.iterdir() if p.suffix == ".py")


def attach_script(tool_id: str, ticket_id: str, script_name: str) -> None:
    """Marks one of list_available_scripts()'s files as applying to this
    ticket. Stores just the filename, not a full path — the fixed folder
    itself is derived from the active repo + tool_id, never per-ticket."""

    def _mutate(t: dict) -> None:
        names = set(t.get("script_names", []))
        names.add(script_name)
        t["script_names"] = sorted(names)

    _update_ticket(tool_id, ticket_id, _mutate)


def detach_script(tool_id: str, ticket_id: str, script_name: str) -> None:
    """Un-marks a script for this ticket — never deletes the actual file
    in validation_scripts_dir(), which may still be attached to other
    tickets or repos."""

    def _mutate(t: dict) -> None:
        names = set(t.get("script_names", []))
        names.discard(script_name)
        t["script_names"] = sorted(names)

    _update_ticket(tool_id, ticket_id, _mutate)


def run_validation_scripts(tool_id: str, ticket: dict) -> tuple[bool, str]:
    """Loads every one of this ticket's attached validation scripts (same
    importlib.util.spec_from_file_location + exec_module mechanism
    QuickData.run_script_file uses) and calls validate() on each. Runs
    every script — doesn't stop at the first failure — so the artist sees
    everything wrong in one message. A script with no validate() defined
    is treated as a pass-through; a script name the ticket still
    references but that's no longer present in the fixed folder (e.g.
    renamed/removed by a TD) is treated as a hard failure, since that's a
    configuration problem worth surfacing rather than silently ignoring."""
    script_names = ticket.get("script_names", [])
    if not script_names:
        return True, ""

    folder = validation_scripts_dir(tool_id)
    failures: list[str] = []
    for script_name in script_names:
        script_path = folder / script_name
        if not script_path.exists():
            failures.append(
                f"{script_name}: no longer found in PublishValidation/{tool_id}/ — "
                "re-check this ticket's attached scripts under Manage Tickets..."
            )
            continue

        module_name = script_path.stem
        try:
            spec = importlib.util.spec_from_file_location(module_name, script_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - a broken validation script must not crash publish()
            failures.append(f"{script_name}: failed to load ({exc})")
            continue

        validate = getattr(module, "validate", None)
        if validate is None:
            print(f"[PublishApi.tickets] {script_name} has no validate() — treating as pass.")
            continue

        try:
            passed = validate()
        except Exception as exc:  # noqa: BLE001 - same reasoning as the load try/except above
            failures.append(f"{script_name}: raised {exc}")
            continue

        if not passed:
            failures.append(f"{script_name}: validate() returned False")

    if failures:
        message = "Publish blocked by validation script(s):\n" + "\n".join(f"- {f}" for f in failures)
        return False, message

    return True, ""
