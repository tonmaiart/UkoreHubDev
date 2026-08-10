# UkoreHub auto-update failed: "local changes to data/projects.json would be overwritten by merge"

## Symptom

`UkoreHub.exe` showed:

```
UkoreHub update failed:
git pull failed: error: Your local changes to the following files
would be overwritten by merge:
        data/projects.json
Please commit your changes or stash them before you merge.
Aborting

You can continue with the current version — restart to retry.
```

This happened on any machine that had an uncommitted local edit to
`data/projects.json` sitting around when `UkoreHub.exe` tried to
self-update.

## Root cause

`data/projects.json`, `data/programs.json`, `data/system_config.json`, and
`data/plugins/core/*.json` were git-tracked and distributed via the same
`git pull` that ships `UkoreHub`'s own code
(`developer/packaging/updater.py:225-229`'s `ensure_up_to_date` — a plain
`git fetch` + `git pull`, no excludes). But the running app also writes to
these exact files locally on every edit — `MetadataStore.save()`,
`ProgramStore.save()`, `SystemConfigStore.save()`
(`core/store.py`/`core/program_store.py`) each blind-overwrote the whole
file from in-memory state on every mutating call, with no commit/push step
at all. So the moment any artist made a local edit (added a repo, changed
a thumbnail, etc.) without a studio admin manually `git commit`+`push`-ing
it upstream first, the next self-update's `git pull` saw an uncommitted
local diff on a file origin/main had also moved forward on, and git
refused to merge rather than risk silently discarding either side. There
was also no locking underneath this — two machines saving at the same
moment already clobbered each other's in-memory state before git even
entered the picture.

## Fix

Moved these four shared JSON stores off git entirely, onto Google Cloud
Storage:

- New `core/cloud_sync.py` (`GcsJsonSync`): `pull()`/`push()` a JSON blob
  to/from a GCS bucket, using object-generation preconditions for
  optimistic-concurrency conflict detection (raises the new
  `core.exceptions.ConflictError` on a losing race, instead of clobbering
  the winner) — kept deliberately isolated so `google-cloud-storage` never
  gets pulled into `developer/packaging/updater.py`'s frozen-exe import
  graph.
- `MetadataStore`/`SystemConfigStore` (`core/store.py`), `ProgramStore`
  (`core/program_store.py`), and `PluginConfigStore`
  (`core/extensibility/config_store.py`) each gained an optional
  `on_save` constructor callback, fired at the end of `save()` —
  `launcher.py` and `interface/plugin_api.py`'s
  `plugin_config_store(shared=True)` wire it to `GcsJsonSync.push`, and
  pull the latest blob before constructing each store.
- `.gitignore` flipped: these four file patterns are now ignored (a local
  cache of the cloud blob) instead of tracked; removed from git with
  `git rm --cached`.

Once these files are no longer git-tracked, the self-update `git pull`
simply never touches them again — the conflict can't recur structurally,
not just because it's now less likely.

## Lesson

Don't git-track a file that the running app also writes to locally without
a commit step, if that same repo is also `git pull`ed by an auto-updater —
any local write becomes an uncommitted diff the next pull can collide
with, and git will (correctly) refuse to silently pick a winner. This
generalizes past `data/*.json`: if a future feature adds another
"studio-shared, app-writes-it-directly" file, git is the wrong sync
mechanism unless something in the app also commits+pushes that specific
write immediately (which nothing here ever did) — either keep it
purely local/per-machine, or sync it through a channel built for
concurrent writers (like `core/cloud_sync.py`'s generation-precondition
push), not through the same tree the app's own code is pulled from.
