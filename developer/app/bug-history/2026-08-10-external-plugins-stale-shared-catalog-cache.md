# 2026-08-10 — External Plugins catalog page showed no entries after adding them, even though Requirements & Plugins showed them fine

## Symptom

User report: catalog entries added via Settings > Developer > External
Plugins stopped showing up on that same page, while Settings > Repo Setting
(Dev) > Requirements & Plugins' External Plugin box (which reads the same
shared catalog file) kept showing them correctly.

## Root cause

`plugins/core/ExternalPlugins/plugin.py`'s `_SyncController` builds one
`ExternalPluginCatalog` (wrapping one `PluginConfigStore(shared=True)`) at
`register(api)` time and holds it for the entire app session, reused by
every `page_factory()` call — this caching was already the shape before the
2026-08-10 auto-sync engine change (see this plugin's README's "Auto-sync
engine"), just previously written to only when a human clicked Add/Edit/
Delete, a rare event.

`PluginConfigStore` (`core/extensibility/config_store.py`) reads the JSON
file into `self._data` once, at construction, and every `.get()` call after
that just returns the in-memory copy — it never re-reads the file on its
own. `core/vcs/cloud_sync.py`'s `GcsJsonSync.push()`, on a 412 Precondition
Failed (someone/something else pushed a newer generation first), re-pulls
the latest blob **over the local file on disk** and raises `ConflictError`
— but has no way to reach back into whichever `PluginConfigStore` instance
that file happened to be loaded into, so that in-memory copy is left
exactly as it was. The new auto-sync engine's `plugin_id` backfill
(`sync_engine.resolve_required_entries`) pushes to this same shared catalog
file automatically on every app start and repo switch — far more often than
the old add/edit/delete-only write path — which made hitting this
conflict-then-stale-cache window realistic instead of theoretical.

Once `_SyncController.catalog`'s in-memory copy diverged from the file on
disk, every subsequent read through it (the External Plugins page's
`refresh_list()`) kept showing the stale snapshot for the rest of the
session, while `interface/repo_settings/requirements_and_plugins_page.py`'s
`_read_external_catalog()` — a plain `json.loads()` off the file, no
caching — kept showing the real, current contents. Reproduced headlessly
(scratch `PluginAPI`/`UkoreCore`, no real `app/data`/`app/cache` touched):
build the catalog once, write a new entry through a *second*, independently
loaded `PluginConfigStore` pointed at the same file (standing in for a
reload-after-conflict), then read through the first one again — it still
reported zero entries even though the file had one.

## Fix

`plugins/core/ExternalPlugins/catalog_store.py`'s
`ExternalPluginCatalog.list_entries()` now calls `self._store.load()`
before reading — always re-reads the file fresh, same "no caching" policy
`_read_external_catalog()` already used. This also means `add_entry()`/
`edit_entry()`/`delete_entry()`/`update_plugin_id()` (which all call
`list_entries()` first to get the current list before mutating) now build
their edit on top of the current file too, instead of a possibly-stale
in-memory snapshot.

## Lesson

A `PluginConfigStore(shared=True)` instance held for a whole app session
(rather than rebuilt per read) is only as fresh as its last `load()` —
anything that changes the backing file without going through that exact
object (another machine's push, or `GcsJsonSync.push()`'s own conflict-pull
reloading the file out from under it) leaves it silently stale for the rest
of the session, with no error and no signal that a re-read is needed. A
long-lived store that's read repeatedly across a session (as opposed to one
built fresh right before each read, like `requirements_and_plugins_page.py`'s
raw JSON read) should call `load()` before every read it does, not just
once at construction — especially once anything automatic (not just a rare
manual click) writes to the same shared file, since that raises the odds of
hitting a push conflict during the session dramatically.
