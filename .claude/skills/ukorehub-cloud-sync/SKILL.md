---
name: ukorehub-cloud-sync
description: Reference for UkoreHub's Cloudflare R2 sync subsystem (C:\Tonmai\UkoreHub) — core/vcs/cloud_sync.py's R2JsonSync, the shared static R2 key baked into UkoreHubLauncher.exe (no per-artist login), and the shared JSON stores (data/projects.json, data/projects/<id>.json, data/programs.json, data/system_config.json, shared=True PluginConfigStore files) that sync through it instead of git. Use this whenever reading, writing, or planning changes to core/vcs/cloud_sync.py, the on_save param on MetadataStore/SystemConfigStore/PluginConfigStore, app/plugins/core/CloudDataAdmin/, developer/launcher/launcher_build/updater.py's R2 env-var injection or r2_credentials.py, or launcher.py's _build_cloud_sync — or whenever the task involves cloud sync, R2, the R2 bucket/key, ConflictError, or "why didn't my change show up on another machine," even if the user doesn't say "cloud" explicitly (e.g. "add a field to system config," "the shared registry isn't syncing," "someone else's edit got lost").
---

# UkoreHub cloud sync — architecture reference

Until 2026-08-09, `data/projects.json`/`programs.json`/`system_config.json`
and every `shared=True` `PluginConfigStore` file were git-tracked, riding
along with `UkoreHub.exe`'s self-update `git pull`. That broke the moment
any machine had an uncommitted local edit: the app's own local write became
an uncommitted diff the next pull could collide with. Don't git-track a
file the running app also writes to locally without a commit step, if the
same repo is auto-updated via `git pull` — either keep such a file purely
local/per-machine, or sync it through a channel built for concurrent
writers (generation-precondition cloud push, see below), not through the
tree the app's own code is pulled from. These files moved onto a cloud
object store instead: same JSON shape, same local files, just a different
sync mechanism — this is the "why" cloud sync exists at all, independent of
which backend it uses.

The sync *backend* changed once more after that: it ran on Google Cloud
Storage with per-artist Google OAuth login for a while, then moved to
**Cloudflare R2 with a single shared static API key** (no per-artist login
at all) — every artist gets equal read/write access the moment they launch
the app. If you see references to GCS, `GcsJsonSync`, `core/google_auth.py`,
`google_oauth_client_id`/`secret`, `gcs_bucket_name`/`project_id`, a
"Studio Setting" window, or a "Login with Google" button anywhere (old
context, old commit messages, stale comments), that's the retired GCS-era
design — none of it exists anymore. This doc describes the current R2
design only.

## What's cloud-synced vs. git-tracked vs. local-only

Before editing anything that reads or writes app config, place it correctly
— getting this wrong means either a change silently never reaches other
machines, or a change gets git-tracked into a file the whole studio
overwrites on every pull.

| Data | Mechanism | Where |
|---|---|---|
| `data/projects.json` (`MetadataStore` index) | Cloud-synced | Blob `projects.json` |
| `data/projects/<id>.json` (`MetadataStore`, per-project) | Cloud-synced | Blob `projects/<id>.json` |
| `data/programs.json` (retired — one-time migration only) | Cloud-synced | Blob `programs.json` |
| `data/system_config.json` (`SystemConfigStore`) | Cloud-synced | Blob `system_config.json` |
| `data/plugins/core/*.json` (`PluginConfigStore`, `shared=True`) | Cloud-synced | Blob `plugins/core/<plugin_id>.json` |
| `assets/thumbnails/`, `assets/program_icons/`, `assets/icons/` | Git-tracked | Binary images, never cloud-synced. See `assets/README.md`. |
| `cache/local_config.json`, `cache/plugin_local_config/*.json` (`shared=False`) | Local-only, gitignored | Per-machine, never synced anywhere |
| `cache/github_token.json` | Local-only, gitignored | Real credential — never open/quote/surface contents |
| `developer/launcher/launcher_build/r2_credentials.py` | Local-only, gitignored | The shared R2 key itself — see "Credential model" below. Not per-machine like the files above; it's the one file whoever *builds* the exe needs, not every artist. |
| `plugins/core/` (the plugin *code* itself) | Git-tracked | Bundled with the app, unrelated to this system |

If a task adds a new **studio-wide** setting, it almost certainly belongs
in `SystemConfigStore` (cloud-synced) or a `shared=True` `PluginConfigStore`
— not a new file, and not `LocalConfigStore`.

## The `on_save` wiring pattern

`MetadataStore`, `SystemConfigStore` (`core/storage/metadata_store.py`,
`core/storage/config_store.py`), and `PluginConfigStore`
(`core/extensibility/config_store.py`) each take an optional constructor
param `on_save: Callable[[], None] | None = None` (`MetadataStore` also
takes `on_delete`), invoked at the end of `save()`. The stores themselves
stay completely backend-agnostic — still plain local JSON read/write via
`atomic_write`, no knowledge of R2 at all. `launcher.py` (for
`MetadataStore`/`SystemConfigStore`) and `interface/plugin_api.py`'s
`plugin_config_store(shared=True)` (for plugin configs) are the only two
places that:

1. Pull the latest blob into the local path *before* constructing the
   store.
2. Pass `on_save=lambda: cloud_sync.push(blob_name, local_path)`.

Adding a new cloud-synced store means repeating this same pull-then-wire
pattern at one of those two call sites — not adding R2 logic to the store
class itself.

## The isolation rule — why `core/vcs/cloud_sync.py` is its own module

**Never import `boto3`/`botocore` from `core/storage/config_store.py`,
`core/storage/metadata_store.py`, `core/extensibility/config_store.py`,
`core/app_core.py`, or anything else reachable from
`developer/launcher/launcher_build/updater.py`'s vendored `core/` import
graph.** That vendored `core/` (`store.py`, `exceptions.py`, `models.py`,
`paths.py`, `theme.py` — near-duplicate copies, not real imports, of a few
of the app repo's own `core/` files) gets bundled into the frozen
`UkoreHubLauncher.exe` PyInstaller build (`build_exe.py`'s plain
`--onefile` build has no hidden-imports list — it just follows
`exe_entry.py`'s/`updater.py`'s own imports). If a cloud dependency ever
got copy-pasted into one of those vendored files, it would need real
PyInstaller hidden-imports surgery to build at all. `core/vcs/cloud_sync.py`
is the only file that imports `boto3`, and only `launcher.py`/
`interface/plugin_api.py` (the *unfrozen* app, run via plain
`python(w).exe`, never the pre-launch exe) import it.

## Credential model — one shared static key, no per-artist login

A single R2 API token (Account ID + Access Key ID + Secret Access Key)
gives every artist equal read/write access — there is no per-artist login
step, unlike the retired Google OAuth design:

- **`developer/launcher/launcher_build/r2_credentials.py`** (gitignored,
  never committed — see `r2_credentials.example.py`, the tracked template)
  holds the four real values (account id, access key id, secret access
  key, bucket name). Whoever builds `UkoreHubLauncher.exe` (`build_exe.py`
  / `git release-launcher`) needs this file present locally; PyInstaller
  bundles it the same way it already bundles `updater.py` and the vendored
  `core/` package — a plain sibling `import`, no `--add-data`/hidden-
  imports change needed. A build without this file still works, just with
  cloud sync disabled for anyone running that exe.
- **`updater.py`**'s `_launch()` (the function that spawns
  `app/launcher.py`) sets `UKOREHUB_R2_ACCOUNT_ID`/
  `UKOREHUB_R2_ACCESS_KEY_ID`/`UKOREHUB_R2_SECRET_ACCESS_KEY`/
  `UKOREHUB_R2_BUCKET_NAME` on the spawned process's environment — same
  pattern as `UKOREHUB_CACHE_DIR`/`UKOREHUB_STORAGE_DIR` — only when
  `r2_credentials.py` actually provided real values.
- **`app/launcher.py`**'s `_build_cloud_sync` reads those env vars
  straight from `os.environ`. Missing any of the three credential vars
  (e.g. the `python launcher.py` direct-invocation dev path, which
  bypasses the exe and its env-var injection entirely) means cloud sync
  is `None` for this run — same "stays local-only" fallback the app has
  always had for "not configured."
- **`core/vcs/cloud_sync.py`**'s `R2JsonSync` builds a `boto3` S3 client
  pointed at `https://{account_id}.r2.cloudflarestorage.com` with the
  access key/secret — no OAuth, no refresh tokens, no per-user identity at
  all.
- The bucket *name* (`r2_bucket_name`) is the only piece that's non-secret
  enough to live in `SystemConfigStore`/`data/system_config.json`
  (cloud-synced) and `appdata/system_config.default.json` (git-tracked
  bootstrap default, same cycle-breaking role `gcs_bucket_name` used to
  play) — the account id/access key/secret never go in any JSON file at
  all, since `system_config.json` is itself one of the things they sync
  (storing them there would be circular, and would also mean every
  artist's local synced-file cache carries the master key in plaintext).

## Conflict handling — `R2JsonSync.pull`/`push`

These stores are still naive whole-file JSON blobs (not a real per-record
schema), so `R2JsonSync` uses S3-style conditional-write preconditions for
optimistic concurrency instead of a document model:

- `pull(blob_name, local_path)` downloads the blob (`get_object`) and
  remembers its ETag. A 404/`NoSuchKey` (nobody's pushed this blob yet) is
  non-fatal — returns `None`, meaning the next `push()` is create-only
  (`IfNoneMatch="*"`).
- `push(blob_name, local_path)` uploads via `put_object` with
  `IfMatch=<last-seen ETag>` (or `IfNoneMatch="*"` for create-only) — not
  `upload_file`, whose `S3Transfer` helper doesn't support these params.
  A rejected conditional write re-pulls the latest into `local_path` and
  raises `core.exceptions.ConflictError` instead of clobbering the winner.
  Cloudflare R2 and AWS S3 don't necessarily report this the same way (412
  `PreconditionFailed`, the plain HTTP spec, vs. AWS's newer 409
  `ConditionalRequestConflict`) — the `except` clause checks both the
  error `Code` and the raw HTTP status, covering either.
- Every R2 call has an explicit `connect_timeout`/`read_timeout`
  (`core/vcs/cloud_sync.py`'s `_TIMEOUT_SECONDS`) — these run
  synchronously on whatever thread calls them (today, the Qt UI thread),
  so an unbounded hang would freeze the whole app. `launcher.py`'s
  `_push_shared_blob`/`interface/plugin_api.py`'s equivalent both let
  `ConflictError` propagate (the UI needs to know) but catch everything
  else (timeout, network, bucket unreachable) and just print a warning —
  a transient cloud problem should never crash or block a routine local
  save, since the local file already saved successfully before
  `on_save()` even fires.
- UI call sites that mutate these stores (`plugins/core/project_editor/`'s
  `project_settings_page.py`/`project_graph_view.py`,
  `interface/settings/program_database_page.py`) catch `ConflictError`
  specifically, call `self.store.load()` to pick up the just-re-pulled
  file, then refresh their display — a plain `except UkoreHubError` alone
  would show the message but leave stale in-memory state.
- **A long-lived `PluginConfigStore(shared=True)` held for a whole app
  session is only as fresh as its last `load()`.** `push()`'s conflict-pull
  rewrites the file on disk but has no way to reach into an already-loaded
  store's in-memory copy — that copy stays silently stale for the rest of
  the session, no error. A store read repeatedly across a session should
  call `load()` before every read, not just at construction, once anything
  automatic (not just a rare manual click) writes to the same shared file.

## No settings UI for cloud sync at all

There is no "Studio Setting" window, no login gate, nothing to configure
per-artist — the old `StudioSettingsDialog`/`plugins/core/CloudConfig/`
plugin was deleted entirely when the shared-key design landed, since a
zero-config shared key leaves nothing for an artist to log into or set.
The only remaining UI touching cloud sync directly is
`app/plugins/core/CloudDataAdmin/` (Settings > Developer > "Cloud Data") —
an admin-only tool for manually pulling/pushing one raw blob to/from a
file the artist explicitly chooses, for restoring an old `data/` backup;
see that plugin's own README.

## Where to look before changing any of this

- `core/README.md` / `core/vcs/README.md` / `core/storage/README.md` /
  `core/auth/README.md` — one-line summaries of the relevant `core/`
  files, including `cloud_sync.py`.
- `app/plugins/core/CloudDataAdmin/README.md` — the one remaining UI
  surface for cloud sync.
- `developer/launcher/README.md` and
  `developer/launcher/launcher_build/r2_credentials.example.py` — how the
  shared key gets built into `UkoreHubLauncher.exe`.
- The `ukorehub-core` skill — the broader `core/` architecture (this skill
  assumes it, doesn't repeat it) — same constructor-injection,
  no-mocking-in-tests conventions apply here too.
