# plugins/studio/PublishApi/

Shared Maya-side library — the single source of truth for "where does a
publish go" and "how do I create the next version folder" — consumed by
`ModelPublisher`, `RigPublisher`, `AnimationPublisher`, and `UkoreBrowser`
(its `core/repo_context.py`). Does not launch Maya; like every other Maya
tool plugin here, `plugin.py` itself exists purely to contribute a
`PYTHONPATH` entry to `plugins/studio/maya_launcher/`'s shared
`maya_launcher_env_bridge` `PluginConfigStore`.

As of 2026-08-03, this is also where the three Publisher plugins' shared
**ticket management** lives (`tickets.py` + `ticket_manager_dialog.py`,
both Maya-side, under `maya-scripts/PublishApi/`) — each Publisher used to
have its own UkoreHub-side Repo Studio Setting tab for a single per-repo
Publish Path choice; that's gone now in favor of user-managed **tickets**,
each with its own Publish Path and validation scripts, created/edited
entirely from inside Maya. See "Tickets" below.

Added 2026-07-19, alongside splitting the original `UkorePublisher` plugin
into `ModelPublisher`/`RigPublisher`/`AnimationPublisher` — see
`plugins/studio/maya_launcher/README.md` for the bridge convention this
follows, and each Publisher plugin's own README for how it's actually used.

**Never gated by `plugins/studio/maya_launcher/`'s per-repo `RepoToolsStore`
toggle** — unlike every other tool plugin listed above, this one has no
legitimate reason to ever be disabled per-repo (it's pure infrastructure,
not an artist-facing feature), and `maya_launcher/plugin.py`'s
`open_maya_file` force-includes its bridge contribution regardless of what
a repo's stored tool list says. See that plugin's README's "Per-repo tool
toggle" section for why — this was added after a repo whose stored list
predated this plugin's existence hit `ModuleNotFoundError: No module named
'PublishApi'` inside `UkoreBrowser/core/repo_context.py`.

## Files

- `manifest.json` — plugin id `publish_api`, entry point `plugin.py`.
- `plugin.py` — `register(api)`: contributes `maya-scripts/` **and**
  `api.app_root` to the shared bridge (same reason
  `plugins/studio/UkoreBrowser/plugin.py` contributes `api.app_root` too —
  so `import core.store`/`core.paths`/`core.extensibility.config_store`
  resolve inside Maya's Python).
- `maya-scripts/PublishApi/repo_paths.py`:
  - `find_ukorehub_root()` — locates the UkoreHub install root from this
    file's own position on disk (`parents[5]` — see the UkoreBrowser
    plugin's own `repo_context.py` for the sibling version of this trick,
    one level deeper because of its extra `core/` subfolder).
  - `get_active_repo()` — `(project, repo, repo_path)` for whichever repo
    UkoreHub currently has active, constructing `LocalConfigStore`/
    `MetadataStore` straight off disk (Maya's Python has no `PluginAPI`
    instance to go through).
  - `get_pipeline_refs()` — every `{"project_id", "repo_id",
    "custom_path_id"}` dict the active repo has connected to via "Connect
    Pipeline Input Path..." in Project Editor, read directly from
    `data/plugins/studio/project_editor.json`.
  - `resolve_ref(ref)` — a pipeline ref (or any `{"project_id","repo_id"}`
    dict) resolved to `(project, repo, repo_path)`.
  - `get_custom_paths(project_id, repo_id)` / `get_custom_path(project_id,
    repo_id, custom_path_id)` — a repo's own declared `CustomPath` catalog
    (`{"id","label","path"}`, `path` relative to that repo's root — see
    `plugins/studio/project_editor`'s `custom_paths_settings_page.py`) and
    a single lookup by id.
  - **Removed 2026-08-03**: `get_chosen_output_ref(tool_id)` and
    `get_publish_root(tool_id)` — the old "one Publish Path per tool per
    repo" resolution. Dead code once all three Publishers moved to
    per-ticket Publish Paths — see `tickets.py`'s
    `get_publish_root_for_ticket(tool_id, ticket)` below, which resolves
    through the same `resolve_ref()`/`get_custom_path()` helpers above,
    just keyed off a specific ticket's own stored choice instead of one
    shared per-repo value.
- `maya-scripts/PublishApi/versioning.py`:
  - `make_sure_folder_exist(path)` — trivial `os.makedirs` wrapper.
  - `get_new_version(base_dir)` — next available `vNNN` integer under a
    directory, by scanning its immediate subfolders.
  - `get_version_directory(publish_root, subfolder, version=None)` —
    creates and returns `(version_dir, version_number)` for
    `<publish_root>/<subfolder>/vNNN/`. `publish_root` is always
    `tickets.get_publish_root_for_ticket(tool_id, ticket)`'s result;
    `subfolder` is the ticket's own `folder_name` (see "Tickets" below).
- `maya-scripts/PublishApi/tickets.py` — user-managed **tickets** shared
  by all three Publisher plugins (see "Tickets" below for the full shape).
- `maya-scripts/PublishApi/ticket_manager_dialog.py` — `TicketManagerDialog`:
  the shared "Manage Tickets..." `QDialog` every Publisher plugin's own
  `interface.py` opens (parameterized by `tool_id`/`tool_label`/
  `show_export_type`) — create/rename/delete tickets, pick each ticket's
  own Publish Path from the active repo's declared pipeline connections
  (same list `repo_paths.get_pipeline_refs()` resolves), a checkable list
  to attach/detach each ticket's validation scripts (checking a box calls
  `tickets.attach_script`/`detach_script` immediately, same
  self-persisting-checkbox convention Requirements/Enable Plugin use), an
  "Open Script Folder..." button (`os.startfile` on
  `tickets.validation_scripts_dir(tool_id)`, for jumping straight to where
  a TD would actually author one), and — only for `AnimationPublisher`
  (`show_export_type=True`) — a Playblast/Unreal Export combo box per
  ticket. "Save Publish Path" is an explicit button, not autosave-on-click
  (same deliberate-commit reasoning the old, now-removed
  `publish_target_settings_page.py` adopted on the UkoreHub side).

## Tickets

Replaces the old "one Publish Path chosen per tool per repo" model
(a UkoreHub-side Repo Studio Setting tab, one choice, applied to every
publish from that repo) with tickets a studio admin creates/manages
**per repo, entirely from inside Maya** via each Publisher's own "Manage
Tickets..." button:

- Each ticket has its own display `name` and its own on-disk `folder_name`
  — kept separate on purpose, and `folder_name` is immutable after
  creation, so renaming a ticket later never moves or breaks its
  already-published version history.
- Each ticket has its own `publish_target` (a pipeline connection ref,
  same shape the old single per-repo choice used) — different tickets on
  the same repo can publish to entirely different destinations.
- Each ticket has a list of attached **validation scripts** —
  `ticket["script_names"]`, filenames referencing `.py` files that live in
  a **fixed** folder, not owned per-ticket: `tickets.validation_scripts_dir(tool_id)`
  = `<active repo's own local clone>/PublishValidation/<tool_id>/`. A TD
  writes/commits the actual scripts there entirely outside this tool (a
  text editor, checked into the repo like any other pipeline code, shared
  to the whole team via that repo's own git history) — "Manage Tickets..."
  only lets a studio admin pick which of the scripts already sitting in
  that folder apply to a given ticket, it never authors one. Each script
  defines one `validate() -> bool` function; all of a ticket's attached
  scripts must return `True` (or be absent/have no `validate()`) for
  `function.py`'s `publish()` to proceed. Modeled after
  `plugins/studio/MayaToolkit/maya-scripts/tmlib/core/QuickData.py`'s
  folder-of-scripts convention (used by the `PythonReader` toolkit,
  formerly "QuickScript") — same `importlib.util.spec_from_file_location`
  + `exec_module` loading mechanism, just calling `validate()` instead of
  `run()` and collecting the bool results instead of discarding them. A
  script name a ticket still references that's since been removed/renamed
  in that folder is a hard failure (not a silent skip) — it means the
  ticket's configuration needs re-checking, not that the check passed.
- `AnimationPublisher` tickets additionally carry an `export_type`
  (`"playblast"` or `"unreal"`) — see that plugin's own README.

Storage: `data/plugins/studio/<tool_id>.json`, key `"tickets"`, keyed by
`"<project_id>:<repo_id>"` (the active repo doing the publishing). This is
the only ticket data that lives under UkoreHub's own `data/` — the
validation scripts themselves deliberately don't, since they're pipeline
code that belongs with the repo, not app config (see above).

**Migration**: the first time a repo's tickets are listed and it still has
an old-style single Publish Path choice (from before 2026-08-03) but no
tickets yet, a `"Main"` ticket is auto-created seeded from that old
choice — nothing gets silently lost by this change.

## Why this replaces the old `share`/`publish` path-swap convention

Before this plugin existed, `UkorePublisher`'s publish root was derived by
string-swapping `.../share/...` for `.../publish/...` in the current Maya
scene's own file path (`UkoreMaya/core/Logic.py`'s `convert_to_publish_path`,
still present in `plugins/studio/MayaToolkit/` — unrelated tools may still
use it, this plugin just doesn't). That convention had no connection to
UkoreHub's own Project/Repo/pipeline model at all — it only worked because
every studio scene file happened to sit under a folder literally named
`share`. `tickets.get_publish_root_for_ticket(tool_id, ticket)` resolves
the destination from Project Editor's actual declared pipeline
**connection** a specific ticket has chosen (e.g. `RigTeam`'s "Main"
ticket resolves to wherever `RigPublish` — the repo it connected to — is
cloned, further scoped down to whichever `CustomPath` that connection
points at, e.g. `RigPublish/Character`), which is correct regardless of
where the artist's local clone happens to live on disk, and keeps
publishing in sync with whatever the studio has declared in Project
Editor's graph.

## Working on this plugin

Read/edit only files under this folder unless the change is specifically
about how `ModelPublisher`/`RigPublisher`/`AnimationPublisher`/`UkoreBrowser`
*consume* this API (a genuine cross-plugin task, not a reason to read them
by default) — see the `ukorehub-plugin` skill.
