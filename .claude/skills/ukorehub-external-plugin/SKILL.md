---
name: ukorehub-external-plugin
description: Strict token-scoping for editing an "external plugin" — an app/cache/plugins/<Name>/ entry (its own separate git clone, e.g. PublishApi, MayaToolkit, UkoreShot, AdvancedSkeleton). When the user says "แก้ external plugin", "edit external plugin <Name>", or names a repo plugin under cache/plugins/ for a feature/fix, read ONLY that plugin's own folder plus developer/app/docs/plugin-api.md — nothing else in this dev repo, not even other docs, unless a real bug forces opening actual app/ source (core/, core_api/, interface/, interface_api/, plugin_api/, or a sibling plugin). Not to be confused with app/plugins/core/ExternalPluginManager/, the in-app catalog/sync manager for these clones — see developer/app/docs/plugins/ExternalPluginManager.md for that plugin instead. Layer this under ukoreshot/ukorehub-maya-plugins when the named plugin is covered by one of those more specific skills.
---

# Editing an external plugin — folder + plugin-api.md only, nothing else

"External plugin" here means an `app/cache/plugins/<Name>/` entry — a
"repo plugin": its own separate git clone with its own remote/history,
not part of this dev repo at all (see root `CLAUDE.md`'s `app/cache/`
entry and the `ukorehub-plugin` skill). Examples: `PublishApi`,
`MayaToolkit`, `UkoreShot`, `RigPublisher`, `AdvancedSkeleton`,
`UkoreReferenceEditor`. Don't confuse this with
`app/plugins/core/ExternalPluginManager/`, the bundled plugin that manages
the *catalog* of these clones (Clone/Pull, auto-sync) — a task about that
catalog page itself is a normal `plugins/core/` task, not this skill; see
`developer/app/docs/plugins/ExternalPluginManager.md`.

## Rule

When the task is "edit/fix/add a feature to external plugin `<Name>`":

1. **Read only two things, in order:**
   - `app/cache/plugins/<Name>/` — the plugin's own folder. Read its
     `README.md` first if it has one, then only the files the task
     actually needs inside that folder (same "don't read the whole tree
     speculatively" discipline as `ukorehub-plugin`).
   - `developer/app/docs/plugin-api.md` — the complete `PluginAPI`
     surface. This is the plugin's *only* legitimate window into the host
     app; it exists specifically so this plugin never needs to open real
     `app/` source to know what's callable.
2. **Do not read anything else in this dev repo** for this task — not
   `app/core/`, `app/core_api/`, `app/interface/`, `app/interface_api/`,
   `app/plugin_api/` source, not a sibling `app/plugins/core/<Other>/` or
   `app/cache/plugins/<Other>/`, not other `developer/app/docs/*.md`
   files, not `plugins-guide.md` — unless the task genuinely needs one of
   those (see exception below). If `plugin-api.md` doesn't cover something
   the plugin needs, that gap is itself worth noting to the user rather
   than quietly reaching past it.
3. **More specific plugin skills win first.** If `<Name>` is `UkoreShot`
   (or `UkorePlayblast`), load `ukoreshot` instead — it already knows that
   plugin's internal subfolder split. If the task touches a
   `maya-scripts/`/`maya-plug-ins/` subfolder inside `<Name>`, also load
   `ukorehub-maya-plugins` for the Maya-specific gotchas. Both are
   narrower than this skill, not a replacement for the "stay in this one
   plugin" rule — they just add domain knowledge this skill doesn't have.

## The one real exception: an actual bug needs real app code

If, while working the task, it turns out the problem isn't in the
plugin's own code but in how the host app itself behaves (a `PluginAPI`
method doesn't do what `plugin-api.md` says, a store isn't persisting,
`interface/` is misrendering something the plugin registered) — that's a
genuine cross-boundary bug, not scope creep. In that case:

- Say explicitly why `plugin-api.md` + the plugin's own folder weren't
  enough before opening anything else.
- Opening `app/core/`, `app/core_api/`, `app/interface/`,
  `app/interface_api/`, or `app/plugin_api/` source directly already
  requires the user's explicit permission — an `ask` rule in
  `.claude/settings.json` per root `CLAUDE.md`. Let that prompt happen
  rather than trying to route around it.
- Afterward, add what you found to `plugin-api.md` (or the relevant doc)
  so the next external-plugin session doesn't need to open real source
  for the same gap — same "update the doc, not just your own context"
  convention `plugin-api.md`'s own header describes.

## Why this is stricter than `ukorehub-plugin`

`ukorehub-plugin` already scopes any single-plugin task to that plugin's
own folder, for both `plugins/core/` and `cache/plugins/`. This skill adds
a second, tighter constraint specific to `cache/plugins/` entries: even
the app-side reference docs are off-limits by default except
`plugin-api.md`, because a repo plugin's code has no legitimate reason to
know about `core-api.md`/`interface-api.md`/`interface.md`/
`plugins-guide.md`/`data-layout.md` internals — everything it's allowed to
touch is already re-exported through `PluginAPI` and documented there. If
a task turns out to need one of those other docs anyway, that's the same
signal as needing real app source: say so, don't default to reading it.
