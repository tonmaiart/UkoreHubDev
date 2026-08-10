# 2026-08-09 — Two Maya-side scripts silently lost the active repo after `local_config.json` moved to `cache/`

## Symptom

Found while working on a different change (moving `MAYA_ENV_BRIDGE_PLUGIN_ID`
to per-project storage), not user-reported yet: `PublishApi.repo_paths.
get_active_repo()`/`resolve_ref()` and `UkoreReferenceEditor.repo_paths.
workspace_root()` — both Maya-side, running under `mayapy` with no
`PluginAPI` instance — would silently return `(None, None, None)`/`None`
for every call, on any machine, regardless of whether a repo was actually
active in UkoreHub. Anything built on top (`PublishApi.repo_paths.
get_pipeline_refs`, `UkoreBrowser.core.repo_context.get_pipeline_root_tabs`,
publish-destination resolution generally) would silently see "no active
repo" too.

## Root cause

`LocalConfigStore` moved from `data/local_config.json` to
`cache/local_config.json` as part of the 2026-08-09 git→GCS cloud-sync
cutover (see
[2026-08-09 — UkoreHub auto-update failed](2026-08-09-shared-data-git-pull-conflict.md)) —
confirmed current at `launcher.py:288`
(`LocalConfigStore(cache_dir / "local_config.json")`) and documented in
`data/README.md`/`cache/README.md`. Two Maya-side files that can't import
`PluginAPI` and construct `LocalConfigStore` straight off disk instead were
never updated to match:

- `plugins/repo_internal/PublishApi/maya-scripts/PublishApi/repo_paths.py`
  (`get_active_repo()`, `resolve_ref()`)
- `plugins/repo_internal/UkoreReferenceEditor/maya-scripts/UkoreReferenceEditor/repo_paths.py`
  (`workspace_root()`)

Both still did `LocalConfigStore(root / "data" / "local_config.json")` —
a path that no longer exists, so `LocalConfigStore.load()` silently falls
back to its all-`None`/empty defaults (same "missing file = defaults, no
exception" convention every store in `core/store.py` uses) rather than
raising. `MetadataStore(root / "data" / "projects.json")` right next to
each of these calls was already correct (that store never moved) — only
`local_config.json`'s new location was missed, since it moved to a
different folder (`cache/`) than the rest.

## Fix

Changed `root / "data" / "local_config.json"` → `root / "cache" /
"local_config.json"` in both files (3 call sites total: 2 in
`PublishApi/repo_paths.py`, 1 in `UkoreReferenceEditor/repo_paths.py`).

## Lesson

When a store's on-disk location moves (`data/` → `cache/`, or any future
reorg), grep isn't enough if you only check `core/`/`interface/` — the
Maya-side `maya-scripts/**/repo_paths.py` files construct these same
stores **directly off disk**, independently, because `mayapy` has no
`PluginAPI` to go through (see `data/README.md`'s "hard rule" section and
[2026-08-05 — Maya tool plugins contributed dead paths to the env bridge](2026-08-05-maya-bridge-tools-hardcoded-stale-plugins-core-root.md)
for the same class of "Maya-side script hardcodes a path, desktop-side
code moves on without it" mistake, just for a different store). This bug
is also the reason `LocalConfigStore`/`MetadataStore` construction
specifically is worth grepping for by class name
(`LocalConfigStore(`/`MetadataStore(`) across the whole repo, not just by
literal path string, after moving any store's file location — a stale
`data/`-vs-`cache/` split like this one produces no exception, no log
line, just a store that quietly loads empty defaults forever.
