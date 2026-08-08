---
name: ukorehub-core
description: Reference for UkoreHub's core/ layer (C:\Tonmai\UkoreHub) — the non-UI data model, git subprocess wrapper, config/data stores, and the plugin extensibility system (hooks, loader, PluginConfigStore, FileOpenerRegistry). Use this whenever reading, writing, or planning changes to core/models.py, core/store.py, core/program_store.py, core/git_service.py, core/github/, or core/extensibility/ — or whenever the task involves UkoreHub plugins, git hooks, or the Project/Repo/Program data model, even if the user doesn't say "core" explicitly (e.g. "add a git hook", "create a new plugin", "what programs does this repo require").
---

# UkoreHub core/ — architecture reference

`core/` is UkoreHub's non-UI layer: **zero PySide6/Qt imports anywhere in
this tree** — that's a deliberate, load-bearing rule, not an accident. It
keeps `core/` importable and testable headlessly (no `QApplication` needed),
and it's how `core/extensibility/hooks.py` gets away with being plain-Python
pub/sub instead of Qt signals. If you're about to add a Qt import to
anything under `core/`, stop — that logic belongs in `interface/` instead,
composed on top of a Qt-free `core/` primitive.

Everything is wired via **constructor injection from `launcher.py`** — no
global singletons, no service locator. `core/` classes take their
dependencies (a `Path`, another store, a `HookRegistry`) as constructor
params, which is exactly why the 121-test suite can construct
`GitService()`, `ProgramStore(tmp_path / "programs.json")`, etc. directly in
tests with zero mocking. Preserve this pattern in new code.

**Before touching anything below, check for a folder README first** —
`core/README.md`, `core/github/README.md`, `core/extensibility/README.md`
are the authoritative, current file listings. This skill is architecture
and *why*, not a file-by-file index; the READMEs are the index.

## Scoped editing

A task about `core/` stays inside `core/` — don't open `interface/` files
unless the change genuinely requires updating a call site there too (e.g. a
`core/store.py` field rename that `interface/` reads).
Within `core/` itself, `github/` and `extensibility/` are independent
clusters (see their own READMEs) — a task about one doesn't need the other
opened. `data/*.json` are the files these stores read/write, not code;
don't open them to "see the data" unless the task specifically needs a
concrete example (and even then, prefer `data/programs.json`/
`data/system_config.json` which are small, over `data/projects.json` which
can grow large with many repos/thumbnails). Never open anything under
`projects/` (the gitignored workspace root of real cloned repos) — see root
`CLAUDE.md`.

## Data model (`core/models.py`)

Plain dataclasses, no behavior — `Project` (has many `Repo`), `Repo`,
`Program` (independent catalog, not owned by a Project). One field on
`Repo` matters a lot for anything plugin-related:

- `required_program_ids: list[str]` — which `Program` catalog entries this
  repo needs (e.g. "Maya 2024"). Resolved via `ProgramStore.get_program(id)`.

Every `from_dict` reads new fields with `.get(key, default)` — follow that
pattern for backward compat if you rename a field (fall back to any
predecessor key name too, when one exists).

## Stores (`core/store.py`, `core/program_store.py`)

All JSON-file stores share one helper: `_atomic_write(path, data)` in
`core/store.py` (tmp-file + `os.replace`) — reuse it, don't hand-roll
another JSON writer.

- `MetadataStore` → `data/projects.json` — the Project/Repo registry.
  **Shared/git-tracked.**
- `SystemConfigStore` → `data/system_config.json` — studio-wide settings
  (currently just the GitHub OAuth client ID). **Shared/git-tracked.**
- `LocalConfigStore` → `cache/local_config.json` — per-machine state
  (workspace root, theme, active repo, recent files). **Gitignored.**
- `ProgramStore` → `data/programs.json` — the shared software catalog
  (`name`, `version`, `description`, `icon_filename`). **Shared/git-tracked.**

The shared-vs-local split (tracked in git vs gitignored) is a recurring
pattern in this codebase — it reappears for `PluginConfigStore`
(`shared=True/False`, writing to `data/plugins/core/` vs
`cache/plugin_local_config/`) and, along a different axis (bundled vs. fetched
separately, not shared-vs-per-machine), for the plugin source roots
themselves: `plugins/core/` and `plugins/repo_internal/` are both
git-tracked and bundled with the app; `cache/plugins/` is gitignored, each
entry its own separate git clone. When adding new per-machine state, put
it in `LocalConfigStore`, not a new file.

## `core/git_service.py`

Wraps `git`/`git-lfs` as subprocess calls (clone, pull, push, commit, stage,
status, conflict resolution, commit log). Takes an optional
`hooks: HookRegistry` in its constructor; `clone`/`pull`/`push`/`commit` each
take an optional keyword-only `context: GitHookContext | None = None` and
fire `GitHookEvent.BEFORE_*`/`AFTER_*`/`*_FAILED` around the operation —
**only when both `hooks` and `context` are provided**, so existing callers
that don't pass `context` are unaffected (this is why none of the original
git-service tests needed updating when hooks were added).

## `core/github/` — GitHub integration

`auth.py` (OAuth Device Flow), `commits_api.py` (REST commit history,
preferred over local `git log` when reachable), `token_store.py`
(keyring-backed, falls back to a gitignored local file). None of the three
import each other; only `auth.py` touches `core.exceptions`.

## `core/extensibility/` — the plugin system

This is the part worth understanding deeply before adding a plugin. Four
files, none importing each other:

- **`loader.py`** — `discover_plugins(roots: list[Path], api_version: int) -> PluginDiscoveryResult`
  scans each root's immediate subdirectories for `manifest.json` +
  an entry-point `.py` file, imports it via `importlib.util.spec_from_file_location`.
  `apply_plugins(discovered, api)` then calls each one's `register(api)`.
  **Never raises** — a bad manifest, version mismatch, or import error is
  recorded as a `PluginLoadFailure` and skipped, so one broken plugin can't
  take down the app. `plugin_source(discovered)` derives `"studio"`/
  `"local"` from `dir_path.parent.name`.
- **`config_store.py`** — `PluginConfigStore(json_path)`: a namespaced,
  free-form-schema JSON store for one plugin's own settings (mirrors
  `LocalConfigStore` but no fixed fields). Two plugins can share data by
  independently constructing a store with the *same plugin_id string* — see
  `plugins/core/maya_launcher/plugin.py` reading
  `plugins/core/software_linker`'s config for a worked example (or
  `plugins/README.md`'s "Sharing data with another plugin" section for the
  general write-up).
- **`hooks.py`** — `GitHookEvent`, `GitHookContext` (`project`, `repo`,
  `repo_path`, `extra`), `HookRegistry` (`subscribe`/`fire`). Deliberately
  plain Python, not `QObject` — see the Qt-free rule above.
- **`file_opener.py`** — `FileOpenerRegistry`/`FileOpenerSpec`: lets a
  plugin claim responsibility for opening a file extension (e.g. launching
  Maya with custom env vars instead of the OS file association) instead of
  the default. `find_opener(path)` matches purely by extension — a plain
  list, not a keyed dict, so duplicate registrations are allowed (first
  match wins), unlike the other registries in `interface/` which reject
  duplicate keys.

## Testing conventions

`pytest.ini` → `testpaths = developer/tests`. Every existing test constructs services
directly with `tmp_path` fixtures — **no mocking framework anywhere in this
repo**. `GitService` tests shell out to real `git init`/`commit`/etc. in
temp directories rather than faking subprocess calls. Match this style for
new `core/` tests. Note: plugin `.py` files (under `plugins/`) are loaded
ad-hoc via `importlib`, not as normal Python packages — they can't be
`import`ed from a normal pytest test file, so their logic isn't covered by
the `developer/tests/` suite unless you extract a pure helper function and load it
via the same `importlib.util.spec_from_file_location` trick a manual
verification script would use.
