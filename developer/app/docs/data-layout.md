# data-layout.md — `app/data/`, `app/appdata/`

Moved here (2026-08-13) from these folders' own `README.md`s, which were
removed — see root `CLAUDE.md`'s "Reading this codebase" section for why.
Covers what's on disk in each and whether it's shared/cloud-synced — see
[`core-api.md`](core-api.md) for the `MetadataStore`/`SystemConfigStore`
classes that own the JSON files described here.

**Don't open files under either of these folders speculatively** —
`data/`'s JSON files are runtime state, worth opening only when a task
needs a concrete current value (debugging a stale value, checking a real
id), not for orientation. No image viewer needed for `data/assets/`
either, same reasoning `assets/` used to carry before it moved here (see
below).

`app/assets/` (thumbnails, program icons; a third subfolder, `icons/` —
static app-chrome icons — was already unused and deleted separately) was
retired entirely on 2026-08-19: those images moved from git-tracked
binary files onto Cloudflare R2, the same cutover the JSON stores went
through on 2026-08-09 and for the same reason — a file the running app
also writes to locally can't safely ride along on the self-update `git
pull`. See `data/assets/` below for where they live now.

## `data/` — cloud-synced blob cache, no exceptions

Mostly JSON (see below), plus `assets/` (binary thumbnail/program-icon
images, pulled lazily instead of eagerly — see its own bullet further
down).

As of 2026-08-14, `data/` itself no longer lives under `app/` — it's
sourced from `DATA_DIR` in `app/launcher.py` (env var `UKOREHUB_DATA_DIR`,
falling back to `~/Documents/UkoreHub/data` only for the raw
`python launcher.py` dev-invocation path), same "survives every self-update
force-reset" treatment `cache/`/`storage/` already had — see root
`CLAUDE.md`'s "Program folder stays program-only" section. The Maya-side
scripts below that hardcode `<found_root>/data/...` (via
`UKOREHUB_APP_ROOT`) have **not** been updated to read `UKOREHUB_DATA_DIR`
instead yet — separate, scoped follow-up per plugin, not done as part of
this move.

Every file directly under `data/` (and `data/projects/*.json`,
`data/plugins/core/*.json`) is a **local cache of a Cloudflare R2 blob**,
synced by `core/vcs/cloud_sync.py`'s `R2JsonSync`: pulled fresh on every
launch, pushed back up on every save (see `launcher.py` and
`plugin_api/plugin_api.py`'s `plugin_config_store(shared=True)`). This
replaced the old model (tracked in this repo, distributed via `git
pull`/Update and Restart) because that meant any machine with an
uncommitted local edit broke the self-update `git pull` outright.
`data/assets/` (below) is the one exception to "pulled fresh on every
launch" — it's still a local R2 blob cache, just pulled lazily per-file
on first read instead, since there's no small fixed list of images to
pull eagerly the way there is for the JSON blobs.

This is a hard rule, not just the common case: a handful of Maya-side
scripts under `cache/plugins/*/maya-scripts/` clones (which can't import
`PluginAPI` — no `boto3` in `mayapy`'s site-packages) build these same
paths themselves, e.g. `root / "data" / "projects.json"` or
`root / "data" / "plugins" / "core" / f"{tool_id}.json"`. Any file placed
directly under `data/` that *isn't* one of these cloud-synced blobs risks
being mistaken by a future reader for one — that's why the two static
git-tracked files that used to live here (`projects.example.json`,
`system_config.default.json`) moved out to `appdata/` instead
(2026-08-09) — see below.

- `projects.json` — `MetadataStore`'s Project/Repo registry, split into a
  **lightweight index** (this file — just `{"id", "name"}` per project) plus
  one blob per project under `projects/<id>.json` (the real payload: each
  project's `repos` with their requirements/pins/etc., plus that project's
  own `programs` — its Program Database, not shared with other projects).
  Editing one project's repos only ever rewrites and pushes that project's
  own `projects/<id>.json`, never this index or any other project's blob —
  keeps the blast radius (and false-conflict risk between artists editing
  unrelated projects) down as the registry grows. **Shared/cloud-synced.**
  Prefer `appdata/projects.example.json`/`appdata/project.example.json` if
  you just need "an example of the shape".
- `projects/<project_id>.json` — one file per project (see above), named
  after the `Project.id` listed in `projects.json`'s index. **Shared/
  cloud-synced**, one R2 blob per file.
- `programs.json` — **retired**, no longer read/written by the running app
  except a one-time migration (`core/storage/metadata_store.py`'s
  `migrate_legacy_programs`, called once from `launcher.py`). Used to be
  the shared, studio-wide Program Database; each Project now has its own
  instead (`Project.programs`, part of that project's own
  `projects/<id>.json` blob). Still pulled at launch and left in place
  afterward as a manual-reference fallback for any Program that no repo
  required at migration time — openable via Settings > Developer > Cloud
  Data (`plugins/core/CloudDataAdmin/`, see
  `developer/app/docs/plugins/CloudDataAdmin.md`).
- `system_config.json` — `SystemConfigStore`, studio-wide settings: GitHub
  OAuth client id, plus `r2_bucket_name` for `core/vcs/cloud_sync.py`. Both
  non-secret identifiers, safe to keep here — the actual R2 account id/
  access key/secret never live in this file at all (would be circular,
  since this file is itself one of the things they sync); see the
  `ukorehub-cloud-sync` skill. Shared/cloud-synced, tiny.
- `plugins/core/*.json` — `PluginConfigStore` files, one per `plugin_id` a
  plugin's `register(api)` chose with `shared=True`
  (`api.plugin_config_store(plugin_id, shared=True)`). Shared/cloud-synced.
  Named after `shared=True/False`, not after which `plugins/` source root
  the calling plugin itself lives under — a `cache/plugins/` plugin still
  writes here for `shared=True`. The `shared=False` counterpart
  (per-machine) writes to `cache/plugin_local_config/*.json` instead —
  `cache/` (gitignored, no README of its own) holds every per-machine file
  UkoreHub owns: `local_config.json`, `github_token.json` (a credential —
  never open/quote/surface its contents), `plugin_local_config/`, and
  `plugins/` (repo plugins, each its own separate git clone).
- `assets/thumbnails/`, `assets/program_icons/` — per-repo thumbnail
  images (filename = `Repo.thumbnail_filename`) and per-`Program` icons
  (filename = `Program.icon_filename`, `core/models.py`). **Cloud-synced,
  but lazily, per-file** — unlike every other entry in this list, these
  aren't pulled eagerly in `launcher.py`'s fixed startup loop, because the
  set of images is unbounded (grows with every repo/program across every
  project) rather than a small fixed list of blobs. Instead
  `MetadataStore.resolve_thumbnail_path`/`resolve_program_icon_path`
  (`core/storage/metadata_store.py`) pull a given image on first read if
  it's not already in the local cache (`on_asset_missing` callback,
  `launcher.py`'s `_pull_asset`), and `set_repo_thumbnail`/
  `set_program_icon` push a newly-picked image right after saving it
  locally (`on_asset_upload` callback, `launcher.py`'s `_push_asset`). R2
  blob keys are `thumbnails/<filename>`/`program_icons/<filename>`. Also
  unlike the JSON stores, a conflicting concurrent upload doesn't raise
  `ConflictError` to the caller — last-write-wins is fine for images, so
  `_push_asset` swallows it. See `core-api.md`'s `MetadataStore` entry.

Everything per-machine/gitignored (`local_config.json`, `github_token.json`,
`plugin_local_config/*.json`, repo-plugin clones) lives under `cache/`
instead, never here. There's no per-artist cloud-sync credential to keep
out of `data/` either — `R2JsonSync` authenticates with a single shared
static key baked into `UkoreHubLauncher.exe` and passed via environment
variables, never written to any JSON file (see
`developer/launcher/launcher_build/r2_credentials.py` and the
`ukorehub-cloud-sync` skill). This means `data/` today holds exactly the
files meant to be identical for everyone at the studio via the shared
bucket — nothing git-tracked, nothing per-machine.

Never confuse `data/projects/` above (per-project JSON metadata blobs)
with `storage/` at the app root, the actual gitignored workspace root
(real cloned repos, binaries, studio artwork) — see root `CLAUDE.md`;
that one is never read at all unless explicitly asked. (`storage/` was
named that specifically, not `projects/`, to keep these two unambiguous.)

## `appdata/` — static bootstrap fallbacks/examples, never cloud-synced

Git-tracked files the app reads as **bootstrap fallbacks or examples** —
never cloud-synced, never written to by the running app. Split out of
`data/` on 2026-08-09 so `data/` could become "cloud-synced JSON blob
cache, no exceptions" literally, instead of true "except for these two
files".

- `system_config.default.json` — bootstrap copy of just the one
  `core/vcs/cloud_sync.py` field a fresh pull needs (`r2_bucket_name`) —
  non-secret, safe to commit; the actual R2 account id/access key/secret
  never live in any JSON file at all. **Is** read by the app: `launcher.py`'s
  `_build_cloud_sync` falls back to it when the real (gitignored)
  `data/system_config.json` doesn't exist yet on this machine or lacks
  `r2_bucket_name` — otherwise a fresh clone could never bootstrap the
  bucket name needed to pull the real `system_config.json` in the first
  place. The first successful pull overwrites `data/system_config.json`
  with the live cloud copy, so this file only matters before that.
- `projects.example.json` — a checked-in sample shape for
  `data/projects.json` — the lightweight index only (`{"id", "name"}` per
  project, `schema_version` 2), **not** read by the app itself.
- `project.example.json` — a checked-in sample shape for one project's own
  blob, `data/projects/<project_id>.json` (repos, requirements, pins,
  plugin_data, and that project's own Program Database) — also **not**
  read by the app itself. Split from `projects.example.json` on
  2026-08-09 when `MetadataStore` itself split the same way — purely a
  reference for a human (or an agent) who needs "an example of the shape"
  without pulling the real, possibly-large `data/projects/<id>.json`.

`thumbnails/`/`program_icons/` (now under `data/assets/`, see above) are
referenced by filename from the JSON stores, same as before the 2026-08-19
move. `MetadataStore` still takes an `assets_dir` constructor param
(default `<data_dir>/assets`) rather than deriving it from `json_path`'s
own folder — that indirection is what let these move independently of the
JSON files' own layout, both times (git → `app/assets/` in the old design,
`app/assets/` → `data/assets/` now).

The static app-chrome icons that used to live at `app/assets/icons/`
(Settings gear, Sidebar tab icons) are gone — the app switched to Qt's
built-in icons, so there was nothing left to migrate for that subfolder.
