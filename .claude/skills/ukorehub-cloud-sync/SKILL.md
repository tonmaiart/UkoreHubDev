---
name: ukorehub-cloud-sync
description: Reference for UkoreHub's Google Cloud Storage sync subsystem (C:\Tonmai\UkoreHub) — core/cloud_sync.py's GcsJsonSync, core/google_auth.py's per-user OAuth login, and the four shared JSON stores (data/projects.json, data/programs.json, data/system_config.json, shared=True PluginConfigStore files) that sync through it instead of git. Use this whenever reading, writing, or planning changes to core/cloud_sync.py, core/google_auth.py, the on_save param on MetadataStore/ProgramStore/SystemConfigStore/PluginConfigStore, interface/settings/studio_settings_dialog.py, or launcher.py's _build_cloud_sync — or whenever the task involves cloud sync, Google login, GCS, the "Studio Setting" window, ConflictError, or "why didn't my change show up on another machine," even if the user doesn't say "cloud" explicitly (e.g. "add a field to system config," "the shared registry isn't syncing," "someone else's edit got lost").
---

# UkoreHub cloud sync — architecture reference

Until 2026-08-09, `data/projects.json`/`programs.json`/`system_config.json`
and every `shared=True` `PluginConfigStore` file were git-tracked, riding
along with `UkoreHub.exe`'s self-update `git pull`. That broke the moment
any machine had an uncommitted local edit — see
`developer/bug-history/2026-08-09-shared-data-git-pull-conflict.md` for the
full incident. These files were moved onto Google Cloud Storage instead:
same JSON shape, same local files, just a different sync mechanism.
**Read that bug-history entry before touching any of this** — it's the
"why," not just a changelog note.

## What's cloud-synced vs. git-tracked vs. local-only

Before editing anything that reads or writes app config, place it correctly
— getting this wrong means either a change silently never reaches other
machines, or a change gets git-tracked into a file the whole studio
overwrites on every pull.

| Data | Mechanism | Where |
|---|---|---|
| `data/projects.json` (`MetadataStore`) | Cloud-synced | Blob `projects.json` |
| `data/programs.json` (`ProgramStore`) | Cloud-synced | Blob `programs.json` |
| `data/system_config.json` (`SystemConfigStore`) | Cloud-synced | Blob `system_config.json` |
| `data/plugins/core/*.json` (`PluginConfigStore`, `shared=True`) | Cloud-synced | Blob `plugins/core/<plugin_id>.json` |
| `assets/thumbnails/`, `assets/program_icons/`, `assets/browser_link_icons/`, `assets/icons/` | Git-tracked | Split out of `data/` into their own `assets/` tree on 2026-08-09, same day as this migration — binary images, never cloud-synced. See `assets/README.md`. |
| `cache/local_config.json`, `cache/plugin_local_config/*.json` (`shared=False`) | Local-only, gitignored | Per-machine, never synced anywhere |
| `cache/github_token.json`, `cache/gcs_refresh_token.json` | Local-only, gitignored | Real credentials — never open/quote/surface contents |
| `plugins/core/`, `plugins/repo_internal/` (the plugin *code* itself) | Git-tracked | Bundled with the app, unrelated to this system |

If a task adds a new **studio-wide** setting, it almost certainly belongs
in `SystemConfigStore` (cloud-synced) or a `shared=True` `PluginConfigStore`
— not a new file, and not `LocalConfigStore`.

## The `on_save` wiring pattern

`MetadataStore`, `ProgramStore`, `SystemConfigStore` (`core/store.py`,
`core/program_store.py`), and `PluginConfigStore`
(`core/extensibility/config_store.py`) each take an optional constructor
param `on_save: Callable[[], None] | None = None`, invoked at the end of
`save()`. The stores themselves stay completely backend-agnostic — still
plain local JSON read/write via `_atomic_write`, no knowledge of GCS at
all. `launcher.py` (for the three main stores) and
`interface/plugin_api.py`'s `plugin_config_store(shared=True)` (for
plugin configs) are the only two places that:

1. Pull the latest blob into the local path *before* constructing the
   store.
2. Pass `on_save=lambda: cloud_sync.push(blob_name, local_path)`.

Adding a new cloud-synced store means repeating this same pull-then-wire
pattern at one of those two call sites — not adding GCS logic to the store
class itself.

## The isolation rule — why `core/cloud_sync.py` is its own module

**Never import `google-cloud-storage` or `google-auth-oauthlib` from
`core/store.py`, `core/program_store.py`, `core/extensibility/config_store.py`,
or anything else reachable from `updater.py (UkoreHubLauncher repo)`'s import
graph.** That module is inside the frozen `UkoreHub.exe`'s PyInstaller
bundle (`build_exe.py (UkoreHubLauncher repo)`'s plain `--onefile` build has no
hidden-imports list — it just follows `exe_entry.py`'s/`updater.py`'s own
imports, which include `core.store`). If a cloud dependency leaked into a
module on that import path, it would get dragged into the frozen exe and
need real PyInstaller hidden-imports surgery. `core/cloud_sync.py` and
`core/google_auth.py` are the only two files that import
`google.cloud.storage`/`google_auth_oauthlib`/`google.oauth2.credentials`,
and only `launcher.py`/`interface/plugin_api.py`/
`interface/settings/studio_settings_dialog.py` (the *unfrozen* app, run via
plain `python(w).exe`, never the pre-launch exe) import those two modules.

## Credential model — per-user OAuth, no service-account key

The studio's GCP organization enforces `iam.disableServiceAccountKeyCreation`
— a downloadable service-account key is not an option, org-wide, not just
for this project. Each artist authenticates as their own Google identity
instead:

- **`core/google_auth.py`**'s `run_installed_app_login(client_id, client_secret)`
  uses `google-auth-oauthlib`'s `InstalledAppFlow.run_local_server()` — the
  loopback flow (RFC 8252): opens the system browser, a short-lived local
  HTTP server catches the redirect, blocks until done, returns a refresh
  token. This is Google's own recommended pattern for a desktop app with a
  real browser and localhost available — **not** the Device Authorization
  flow (device code + manual entry), which is a clunkier fit here and was
  the first (later replaced) implementation; if you see references to
  `request_device_code`/`poll_for_token`/"TVs and Limited Input devices" in
  old context, that's stale — the OAuth client type is **"Desktop app."**
- **`GoogleTokenStore`** (same file) persists the refresh token via the OS
  keyring, falling back to a gitignored `cache/gcs_refresh_token.json` —
  same keyring/fallback-file shape as `core/auth/token_store.py`'s
  `SecureTokenStore`, which is in fact the same shared class now (one
  `SecureTokenStore` used for both GitHub's and Google's tokens, see
  `core/auth/README.md`).
- **`core/cloud_sync.py`**'s `GcsJsonSync` builds a
  `google.oauth2.credentials.Credentials` from the stored refresh token +
  `client_id`/`client_secret`/`project_id` and hands it to
  `storage.Client(project=..., credentials=...)` — `google-auth` refreshes
  the short-lived access token automatically, no manual refresh call
  needed.
- Non-secret identifiers (`gcs_bucket_name`, `gcs_project_id`,
  `google_oauth_client_id`, `google_oauth_client_secret` — a "Desktop app"
  client secret isn't meaningfully confidential for a distributed app, same
  footing as the already-committed `github_client_id`) live in
  `SystemConfigStore`/`data/system_config.json`, cloud-synced like
  everything else there. The actual per-machine refresh token is the only
  real secret, and it never touches `data/`.

## Conflict handling — `GcsJsonSync.pull`/`push`

These stores are still naive whole-file JSON blobs (not a real per-record
schema), so `GcsJsonSync` uses GCS object-generation preconditions for
optimistic concurrency instead of a document model:

- `pull(blob_name, local_path)` downloads the blob and remembers its
  generation number. A 404 (nobody's pushed this blob yet) is non-fatal —
  returns `0`, meaning the next `push()` is create-only.
- `push(blob_name, local_path)` uploads with
  `if_generation_match=<last-seen generation>`. A 412 Precondition Failed
  (someone else wrote a newer generation first) re-pulls the latest into
  `local_path` and raises `core.exceptions.ConflictError` instead of
  clobbering the winner.
- Every GCS call has an explicit `timeout` (`core/cloud_sync.py`'s
  `_TIMEOUT_SECONDS`) — these run synchronously on whatever thread calls
  them (today, the Qt UI thread), so an unbounded hang would freeze the
  whole app. `launcher.py`'s `_push_shared_blob`/`interface/plugin_api.py`'s
  equivalent both let `ConflictError` propagate (the UI needs to know) but
  catch everything else (timeout, auth failure, no network) and just print
  a warning — a transient cloud problem should never crash or block a
  routine local save, since the local file already saved successfully
  before `on_save()` even fires.
- UI call sites that mutate these stores (`plugins/core/project_editor/`'s
  `project_settings_page.py`/`project_graph_view.py`,
  `interface/settings/program_database_page.py`) catch `ConflictError`
  specifically, call `self.store.load()` to pick up the just-re-pulled
  file, then refresh their display — a plain `except UkoreHubError` alone
  would show the message but leave stale in-memory state.

## `StudioSettingsDialog` — deliberately not a Settings tab

`interface/settings/studio_settings_dialog.py`'s `StudioSettingsDialog` is
where an artist configures/logs into cloud sync. It is **not** a
`SettingsTabSpec` and does not live inside the normal `SettingsDialog`
popup (`interface/settings/settings_view.py`) — it's its own top-level
window, opened via a separate **"Studio"** button in `Sidebar`'s footer
(`interface/sidebar/sidebar.py`), next to but distinct from the gear-icon
Setting button. Two deliberate departures from every other page in
`interface/settings/` (which all self-persist on every field blur, no
Save/Cancel — see `interface/settings/README.md`):

1. **A login gate.** Shown only until a Google refresh token is first
   cached (`GoogleTokenStore.load_token()`); after that, every later open
   goes straight to the full form — the gate never reappears just because
   Settings was reopened.
2. **An explicit Save button.** Fields buffer locally and only persist to
   `SystemConfigStore` when Save is clicked — an accidental edit here would
   repoint the whole studio's shared registry sync, not just one
   machine's own preference, so it doesn't get the same "save on blur"
   treatment as e.g. workspace folder or theme.

If a task touches Google/GCS-related Settings UI, it's almost certainly in
this file, not `interface/settings/github_oauth_settings_page.py` (which
reverted to just the plain GitHub OAuth Client ID field once the Google/GCS
fields moved out here).

## Where to look before changing any of this

- `core/README.md` — one-line summary of every file in `core/`, including
  `cloud_sync.py` and `google_auth.py`.
- `interface/settings/README.md` — the Settings popup's self-persisting
  convention, and why `StudioSettingsDialog` is the one exception.
- `interface/sidebar/README.md` — the footer button layout.
- `developer/bug-history/2026-08-09-shared-data-git-pull-conflict.md` — the
  incident that started this whole migration.
- The `ukorehub-core` skill — the broader `core/` architecture (this skill
  assumes it, doesn't repeat it) — same constructor-injection,
  no-mocking-in-tests conventions apply here too.
