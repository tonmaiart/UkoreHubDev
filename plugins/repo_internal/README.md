# plugins/repo_internal/

Bundled with the app exactly like `plugins/core/` — git-tracked, shipped
via `self_update.py`'s whole-tree `git pull`, no separate fetch — but
gated **opt-in** per repo instead of `core/`'s opt-out. A plugin here stays
hidden for every repo until that repo explicitly requires it
(`Repo.required_plugin_ids`, set from Settings > Repo > Enable Plugin,
`interface/repo_settings/enable_plugin_page.py`), the same "off until
required" shape as a `core/program_store.py` Program requirement. See
`plugins/README.md` for how this compares to `plugins/core/` and
`cache/plugins/`, and `core/extensibility/README.md` for the discovery
mechanics (`core/extensibility/loader.py`'s `plugin_source()` returns
`"repo_internal"` for anything discovered here).

Use this folder instead of `plugins/core/` for a plugin that only some
repos actually need — adding a plugin to `core/` turns it on for every
existing repo immediately (opt-out), which is the wrong default for
something niche; adding it here instead keeps every existing repo
unaffected until a repo owner opts in.

Same authoring shape as any other plugin (`manifest.json` + `plugin.py`
with `register(api)`, optionally a real Python package for a multi-file
plugin — see `plugins/README.md`'s "Minimum folder shape" and "Multi-file
plugins" sections). Empty as of 2026-08-04 — no plugin has moved here yet.
