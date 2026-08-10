# External Plugins' per-project filter silently emptied Requirements & Plugins for existing catalog entries

## Symptom

User report: "external plugin ยังไม่แสดงขึ้นมาให้ติ้กใน repo setting" (external
plugins still don't show up to check in Repo Setting) — the studio's
existing `cache/plugins/` catalog entries (UkoreShot, MayaLauncher,
UkoreReferenceEditor, ...), all visible on Settings > Developer > External
Plugins, were completely absent from Settings > Repo Setting (Dev) >
Requirements & Plugins' "External Plugin" box for a project that had never
selected any of them.

## Root cause

Same-day, two-step change:

1. A 2026-08-10 feature added a per-project pre-filter: Requirements &
   Plugins' External column only listed a catalog entry if it was in the
   active Project's `Project.plugin_data["external_plugins"]
   ["selected_entry_ids"]`, set via a manual "Used by this Project"
   checkbox on the External Plugins catalog page.
2. Later the same day, in response to feedback that the manual checkbox was
   a redundant click ("ทุกอันที่ add เข้าไป คือมัน used by this project
   อยู่แล้ว" — everything added is already used by this project), the
   checkbox was replaced with automatic selection: `_auto_select_entry` ran
   right after `_on_add`/`_on_edit` added or adopted a catalog entry.

The flaw survived both versions: `selected_entry_ids` is empty by default
for a project, and nothing ever backfills it for entries that were already
in the catalog *before* either version of this feature existed (or before
they were viewed under the now-active project). Auto-select only fires on
a fresh Add or an Edit-adopt of a "(not catalogued)" row — never on an
already-catalogued entry. With no manual checkbox left to opt an existing
entry in (removed in step 2) and no automatic path either, a project that
had never triggered Add/Edit for those entries saw an empty External list
despite a fully populated studio-wide catalog.

## Fix

Reverted the per-project filter entirely rather than patching it a third
time (e.g. an explicit "Use in this Project" button) — per the same user
feedback that started this, the studio's actual usage pattern is "every
catalogued entry is relevant to every project" anyway, so the filter was
solving a problem that didn't match real usage:

- `plugins/core/ExternalPlugins/external_plugins_page.py` — removed
  `_auto_select_entry`/`_selected_entry_ids`/`_catalog_entry_by_folder`/
  `_active_project_id` and the `store`/`local_config_store` constructor
  params that only existed to support them.
- `plugins/core/ExternalPlugins/plugin.py` — stopped threading
  `api.metadata`/`api.local_config` into `ExternalPluginsPage`.
- `interface/repo_settings/requirements_and_plugins_page.py` —
  `_rebuild_plugin_lists`/`_add_pending_external_items` now list every
  discovered "repo"-source plugin and every catalog entry directly (via
  `_read_external_catalog()`), no `selected_entry_ids` filtering; removed
  `_selected_external_catalog_entries` and the `_NOT_SELECTED_SUFFIX` label.

## Lesson

A feature that gates a list on "has this been explicitly opted into yet"
needs a migration/backfill story for records that predate the gate — or a
way for a user to opt an existing record in after the fact. Replacing a
manual opt-in control with an automatic one (as step 2 did) can silently
remove the *only* remaining path for pre-existing records to ever satisfy
the gate, since automatic selection is usually keyed to a specific
user action (Add, Adopt) that already-catalogued records won't trigger
again. When a filter's coverage depends on "this thing was created via
this specific code path," audit what happens to things that existed before
the filter — don't assume a list starts empty and only grows through the
paths you just wired up.
