# developer/app/docs/

Reference docs for `app/` subsystems — consolidated here (2026-08-13) from
what used to be a `README.md` in every `app/` subfolder (removed; see root
`CLAUDE.md`'s "Reading this codebase" section for why: upkeep tokens on
dozens of scattered READMEs cost more than the orientation they saved).
Read the relevant doc below before opening a source folder speculatively
just to get oriented — each one exists so a session can answer "how do I
use X"/"what's in here" without opening every file in X.

- [`core-api.md`](core-api.md) — `app/core_api/` (the `UkoreCore` facade
  `app/interface/`, `app/launcher.py`, and `app/plugin_api/`'s own facade
  files use instead of importing `app/core/` directly) **and** an "Inside
  `core/`" orientation section covering `app/core/` itself. Read this
  before opening either `app/core/` or `app/core_api/` — both require the
  user's explicit permission to read (`ask` rules in
  `.claude/settings.json`), per root `CLAUDE.md`'s rule.
- [`plugin-api.md`](plugin-api.md) — complete command reference for
  `app/plugin_api/` (the `PluginAPI` facade + registries every
  `app/plugins/core/<Name>/` plugin uses). Same before-opening/`ask`-permission
  rule, for `app/plugin_api/`.
- [`interface-api.md`](interface-api.md) — complete command reference for
  `app/interface_api/` (the facade `app/launcher.py` and
  `app/plugin_api/__init__.py` use instead of importing `app/interface/`
  directly). Read this before opening either `app/interface/` or
  `app/interface_api/` — both require the user's explicit permission to
  read (`ask` rules in `.claude/settings.json`), per root `CLAUDE.md`'s
  rule.
- [`interface.md`](interface.md) — structure/orientation reference for
  `app/interface/` (main app shell, `sidebar/`, `repo_settings/`,
  `settings/`, `shared/`).
- [`plugins-guide.md`](plugins-guide.md) — how to author a plugin
  end-to-end (manifest.json shape, multi-file import conventions,
  cross-plugin data/UI sharing, testing). Companion to `plugin-api.md`
  (that one's the command reference; this one's the authoring guide).
- [`plugins/`](plugins/) — one doc per `app/plugins/core/<Name>/` plugin's
  own implementation details (`CloudDataAdmin.md`, `DebugConsole.md`,
  `ExternalPluginManager.md`, `explorer.md`, `project_editor.md`,
  `software_linker.md`, `submit.md`). Kept as separate files, not merged
  into one, so working on a single plugin only needs that plugin's own doc
  — see the `ukorehub-plugin` skill's "never open a sibling plugin's
  source" discipline, which applies the same way to these docs.
- [`data-layout.md`](data-layout.md) — what's on disk under `app/data/`,
  `app/appdata/`, `app/assets/` and whether it's shared/cloud-synced.
