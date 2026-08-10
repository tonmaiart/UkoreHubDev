# UkoreHub (dev repo)

This is the merged dev repo for UkoreHub: [`app/`](app/README.md) is the
actual pipeline tool (a Git repo launcher built on PySide6 — see
[app/README.md](app/README.md) for the full project overview,
prerequisites, and config split), and `developer/` is dev-only tooling,
split into [`developer/app/`](developer/app/README.md) (app-specific docs/
tests) and [`developer/launcher/`](developer/launcher/README.md)
(`UkoreHubLauncher.exe`'s own source). See "Merged-repo structure" below
for how this fits together and why.

**Before acting on a casual/colloquial term the user uses for a feature**
(e.g. "the program's setting", "Viewgraph", "Custom Path") **or before
asking a clarifying question about one, read
[developer/app/GLOSSARY.md](developer/app/GLOSSARY.md)
first** — it maps terms that are easy to misread onto the actual feature/
file, recorded specifically because one of these got misread once already
(see its own entries for the incidents). If a term isn't in there and the
mapping is genuinely ambiguous, ask the user rather than guessing — and
add the resolved mapping to `developer/app/GLOSSARY.md` afterward so it
doesn't need asking again.

**Before changing code in a file or area listed in
[developer/app/bug-history/README.md](developer/app/bug-history/README.md)'s
index (for `app/`) or
[developer/launcher/bug-history/README.md](developer/launcher/bug-history/README.md)'s
index (for `developer/launcher/`), read that entry first** — each one ends
with a "Lesson" describing a reusable mistake pattern (e.g. a specific
circular-import shape, a specific stale-path bug), not just a one-off
incident. After fixing any real bug (a crash, a silent failure, wrong
behavior — not a feature change), add a new entry to whichever
`bug-history/` matches the area you fixed, following its own "Adding a new
entry" format, so the next change in that area doesn't reintroduce it.

## Reading this codebase

Before exploring a folder's `.py` files, check whether it has its own
`README.md` (e.g. [app/core/README.md](app/core/README.md),
[app/interface/README.md](app/interface/README.md)) and read it first — it
gives a short, current summary of what that folder is responsible for and
how its files relate, which makes the individual files much faster to
place in context.

**Every folder should have a `README.md`.** This is a token-budget rule,
not just documentation: a good folder README lets a session understand
what's inside without opening every file in it. When you create a new
folder (a new `app/plugins/core/<Name>/`, a new subfolder under
`app/core/` or `app/interface/`), add a short `README.md` to it in the same
style as the existing ones (see `app/core/README.md` for the reference
tone/format — a short intro paragraph, then a flat bullet list of what
each file/subfolder does and how they relate).

## Scoped editing — stay inside the folder the task names

When a task is about one specific area — a single `app/plugins/core/<Name>/`,
`app/cache/plugins/<Name>/`, `app/core/`, `app/interface/`,
`developer/app/`, or `developer/launcher/` — read and edit only that
folder. Don't open sibling folders "just in case" unless the task
genuinely crosses the boundary (e.g. an `app/core/` change whose call sites
in `app/interface/` also need updating). Concretely:
- Told to fix/change a plugin (Explorer, Submit, SoftwareLinker,
  MayaLauncher, or a new one) → touch only its own
  `app/plugins/core/<Name>/` or `app/cache/plugins/<Name>/` folder. See the
  `ukorehub-plugin` skill and `app/plugins/README.md` — never open a
  sibling plugin's source, and cross-plugin data/UI coordination goes
  through the documented `plugin_config_store`/`UICommandService`
  conventions, not imports.
- Told to fix/change `app/core/` → touch only `app/core/` unless the
  change requires updating an `app/interface/` call site.
- Told to fix/change `app/interface/` → touch only `app/interface/` unless
  the change requires an `app/core/` addition it depends on. Note
  Explorer/Submit are `app/plugins/`, not `app/interface/`, despite
  showing up as ordinary tabs — see the plugin bullet above instead.
- Told to fix/change the launcher exe, its self-update logic, or its build
  tooling → touch only `developer/launcher/`. Never edit `app/` for a
  launcher-side task — the launcher (`developer/launcher/launcher_build/`)
  intentionally vendors near-duplicate copies of a few `app/core/` files
  rather than importing them (see `developer/launcher/README.md`); a
  change to the real ones needs a manual, separate mirror there, not a
  cross-folder edit in the same task.
- Told to fix/change dev tooling for the app (bug-history, GLOSSARY,
  tests) → touch only `developer/app/`.

## Testing — only when explicitly requested

Do not run `pytest`, headless smoke-test scripts, or import-sweep checks
after a change unless the user explicitly asks for testing/verification in
that turn. Skipping this step makes iteration noticeably faster, and the
user will ask for it by name when they want it. This applies even to
changes that would normally warrant self-verification (UI rewiring,
renamed modules, registry changes) — implement the change, report what
changed, and stop there.

## Headless/smoke testing — never point at real `app/data/`/`app/cache/`

If you need to construct real app objects (`MetadataStore`,
`LocalConfigStore`, `MainWindow`, etc.) outside of `pytest` — e.g. a
throwaway headless smoke-test script to verify wiring after a
registry/constructor change — **never point them at the repo's real
`app/data/`/`app/cache/` directories or the real app `REPO_ROOT`
(`app/`)**. Copy them into a scratch/tmp directory first and construct
everything against that copy instead. `app/cache/local_config.json` can
have a real `active_repo_id` saved, which makes `MainWindow.__init__` kick
off a real background git sync (`MainWindow._start_auto_sync`, delegating
to `app/plugins/core/submit/repo_git_status_page.py`'s
`RepoGitStatusPage.sync_active_repo`) on a background `QThread` that starts
running the moment `.start()` is called, independent of whether
`app.exec()` ever runs. A real `UkoreHubLauncher.exe` /
`app/launcher.py` instance may also be running concurrently on the studio
machine you're working on — check for one (e.g. `tasklist`) before assuming
any change to a shared JSON store is safe to discard or revert.
`pytest`'s own tests are unaffected by this — they already use `tmp_path`.

## Program folder stays program-only — user/project data never lives under `app/`

`app/cache/` and `app/storage/` (see their entries below) are per-machine,
per-user data — never something the installed app folder should own.
`UkoreHubLauncher.exe` normally points the `UKOREHUB_CACHE_DIR` /
`UKOREHUB_STORAGE_DIR` env vars outside `app/` before spawning
`app/launcher.py` (in a real, non-dev install — see "Launcher dev mode"
below for how this dev repo's own copy of the exe differs). When those
aren't set — the `python app/launcher.py` direct dev-invocation path,
which bypasses the exe entirely — `launcher.py` falls back to
`~/Documents/UkoreHub/cache` and `~/Documents/UkoreHub/storage`
(`USER_DATA_DIR` in `launcher.py`), **not** `app/cache` / `app/storage`.
The app folder must contain only the program itself, so a real update can
wipe/replace it wholesale (see `developer/launcher/README.md`) without
risking or silently orphaning real user/project data next to the new copy.
Never reintroduce an `app/`-relative default for either path — any new
per-machine or per-user data directory added later must default outside
`app/` the same way, not join `app/cache/`/`app/storage/` as a sibling
under the app folder.

## Merged-repo structure

Two separate GitHub *release* repos, but only **one** dev repo (this one,
`UkoreHubDev`, remote `origin`) — day-to-day work on either side happens
directly on this repo's `main`, no `dev` branch:
- **`UkoreHub`** (remote `release`) — a clean mirror of this repo's `app/`
  contents (flattened to look like a plain checkout), minus `developer/`
  and `.claude/` since those never exist there in the first place. This is
  what artists' `UkoreHubLauncher.exe` installs actually clone/pull.
- **`UkoreHubLauncher`** (remote `release-launcher`) — holds only the
  built `UkoreHubLauncher.exe` at its root. Edited only via
  `developer/launcher/` in this repo now (previously its own separate dev
  repo, `UkoreHubLauncherDev` — merged in here so there's one dev repo
  instead of two; that old standalone repo still exists as an untouched
  archive but is no longer where launcher work happens).

Publishing is exactly two commands (git aliases, per-machine — see
`developer/README.md` if they're not configured yet):
```
git release-app         # app/ → UkoreHub (release)
git release-launcher    # rebuilds the exe, then → UkoreHubLauncher (release-launcher)
```
Each does: add + commit + push this repo's own `main` to `origin`, then
publish (with dev-only files stripped/never-included) to its own release
remote. See `developer/release_app.ps1` / `developer/release_launcher.ps1`
for the exact mechanics, and `developer/README.md` for the full writeup.

## Launcher dev mode

The `UkoreHubLauncher.exe` tracked at this repo's own root is a real,
runnable copy — double-click it (or run it) from here to test `app/`
changes through the real pre-launch flow (prereq checks, GitHub login,
workspace picker) without waiting on a release. It detects that it's
running against this dev repo (a `developer/` folder next to it — never
present in a real artist install) and skips both self-update steps
entirely: it never touches this repo's own git state, and never tries to
bootstrap/hard-reset `app/` as if it were an independent clone of the
`UkoreHub` release repo — see
`developer/launcher/launcher_build/updater.py`'s `_is_dev_checkout`. A real
install (no `developer/` folder) is unaffected — its self-update behavior
is exactly as before. Rebuild after changing
`developer/launcher/launcher_build/updater.py`/`exe_entry.py` — PyInstaller
bakes the source in, so an unrebuilt exe still runs the old logic (see
`developer/launcher/README.md`).

## Project layout

- `app/core/` — non-UI logic: metadata store, git operations, GitHub auth, theming.
- `app/interface/` — PySide6 GUI: sidebar, pages, dialogs, background workers.
- `app/data/` — cloud-synced JSON blob caches only (`projects.json` — an
  index, real payload in `projects/<id>.json` per project, each with its
  own Program Database — `system_config.json`, `plugins/core/*.json`, and a
  retired `programs.json`, see `app/data/README.md`), no exceptions —
  several Maya-side scripts under `app/cache/plugins/` clones hardcode
  these exact `data/` paths directly (they can't import `PluginAPI`), so
  nothing else belongs here. See [app/data/README.md](app/data/README.md)
  — don't open these unless the task needs a concrete current value.
- `app/assets/` — git-tracked binary images (`thumbnails/`, `program_icons/`,
  `icons/`), never cloud-synced. See
  [app/assets/README.md](app/assets/README.md) — never open an image file in here.
- `app/appdata/` — static git-tracked bootstrap defaults/examples
  (`system_config.default.json`, `projects.example.json`), never
  cloud-synced and never written by the running app. See
  [app/appdata/README.md](app/appdata/README.md).
- `app/plugins/` — UkoreHub's own sub-systems: `app/plugins/core/`
  (bundled, always-on for every repo) and `app/cache/plugins/` (each its
  own separate git clone, off-by-default, opt-in per repo). See
  `app/core/extensibility/README.md` for the discovery mechanism and
  `app/plugins/README.md` plus the `ukorehub-plugin` skill for the "stay
  inside one folder" editing discipline it uses.
- `app/cache/` — every per-machine, gitignored file UkoreHub owns (actual
  on-disk location is `CACHE_DIR`, set by `launcher.py` — see "Program
  folder stays program-only" above, **not** necessarily under `app/`):
  `local_config.json`, `github_token.json` (a credential — never open,
  quote, or otherwise surface its contents),
  `plugin_local_config/`, and `plugins/` — **repo plugins**: each entry is
  its own separate git clone (own remote/history, not part of this repo at
  all), fetched/updated on demand only for a repo that requires it. Never
  read or list files under `app/cache/` unless the task explicitly needs
  to (e.g. names a repo plugin by folder name) — same reasoning as
  `app/storage/` below, this is fetched/generated/runtime content, not
  something to explore speculatively (though unlike `app/storage/`, an
  `app/cache/plugins/` entry's plugin.py/manifest.json are real code worth
  reading when a task is actually about that specific plugin — see
  `app/plugins/README.md`). See [app/cache/README.md](app/cache/README.md)
  for the full breakdown.
- `app/storage/` — **the actual workspace root**, pointed to by
  `app/cache/local_config.json`'s `workspace_root` (actual on-disk location
  is `STORAGE_DIR`, set by `launcher.py` — see "Program folder stays
  program-only" above, **not** necessarily under `app/`): real cloned
  production repos (Maya/Blender scenes, huge binaries, studio artwork),
  gitignored. Named `storage/`, not `projects/`, specifically so it can't
  be confused with `app/data/projects/` (the per-project metadata blobs —
  see [app/data/README.md](app/data/README.md)). **Never read or list
  files under here unless the user explicitly asks** — there is no code in
  it, it can be enormous, and its contents are production data, not
  something to explore speculatively.
- `app/launcher.py` — the app's own entry point (`python app/launcher.py`
  direct-invocation dev path; a real install spawns this from
  `UkoreHubLauncher.exe` instead — see "Launcher dev mode" above).
- `developer/app/tests/` — pytest suite (`pytest.ini` at repo root points
  `testpaths` here, with `pythonpath = app` so its `from core...`/
  `from interface...` imports resolve against `app/`). Not released — see
  `developer/app/README.md`.
- `developer/launcher/launcher_build/` — `UkoreHubLauncher.exe`'s own
  source (`exe_entry.py`, `updater.py`, `build_exe.py`, `icon.ico`, and a
  small vendored `core/`). Not released either — only the exe it builds
  is. See `developer/launcher/README.md`.
- `UkoreHubLauncher.exe` (repo root) — the built launcher, git-tracked here
  deliberately (rebuilt via `developer/launcher/launcher_build/build_exe.py`,
  or via `git release-launcher`). See "Launcher dev mode" above.
