# agent_bridge (`app/plugins/core/AgentBridge/`)

Lets a local AI agent (jcoopy, Merdera Project's pipeline agent) drive
UkoreHub the way an artist does, so whatever it opens gets the full
pipeline setup: linked program, per-repo tool env, launch hooks,
`setProject`. Added 2026-11-04.

## Switch

Off by default, **per machine**: Settings > Developer > **Agent Bridge**
checkbox, stored as `enabled` in the per-machine
`plugin_config_store("agent_bridge")`
(`cache/plugin_local_config/agent_bridge.json`). Toggling starts/stops the
server immediately; when on at launch it starts from `on_app_start`.

## Transport

- `QTcpServer` on `127.0.0.1`, random port, signals on the UI thread.
- On start it writes `<cache_dir>/agent_bridge/session.json`:
  `{port, token, pid, started}` (deleted on stop / app close). Only a
  client that can read that file (same user, same machine) has the token.
- One JSON object per line: `{"token", "cmd", "args"}` →
  `{"ok": true, "result": ...}` or `{"ok": false, "error": ...}`. A
  connection can send several requests.
- Every command is logged to the `AgentBridge` logger (DebugConsole) and to
  the settings tab's "Recent commands" list.

## Commands

| cmd | args | does |
| --- | --- | --- |
| `ping` | — | pid, app root, workspace root, active project/repo ids, loaded plugin ids |
| `describe` | — | public attribute names of `metadata`, `local_config`, `file_opener_registry`, `program_launch_registry` (API discovery without reading `core/`) |
| `list_repos` | — | active project's repos: id, name, local_path, absolute path, exists, required_plugin_ids |
| `open_file` | `path`, opt. `repo`, `post_mel`, `post_python_file` | opens through `file_opener_registry.find_opener()` — `.ma/.mb` → `maya_launcher`. Repo defaults to the one whose folder contains `path`. `post_*` run in Maya after the scene opens (see below) |
| `launch_program` | `program` (name or id, e.g. `"Autodesk Maya"`), `repo`, opt. `post_mel`, `post_python_file` | `program_launch_registry.find_launcher()` (returns the launch callable itself) → `launch(repo)` |
| `list_programs` | — | active project's Programs: id, name |
| `history` | opt. `limit` | recent command log |
| `list_file_actions` | — | every registered `FileContextActionSpec`: key, label |
| `file_action` | `key`, `paths` (str or list) | runs that spec's `run(paths)` directly, skipping `match()` (added 2026-11-22) |

**`file_action` is how the bridge reaches another plugin's work.** Plugins
can't import each other and `plugin_api` has no shared-callable registry, but
`file_context_action_registry` holds callables by key. A plugin that wants to
offer agent work registers a `FileContextActionSpec` whose `match` is always
`False` (so it never shows in Explorer's menu) and takes request files as
`paths`. First user: MayaPublisher's `maya_publisher_agent_batch` (headless
batch publish from a request `.json`, see that plugin's README). Runs on the
UI thread like every command, which a `QProcess`-based queue needs.

`post_mel` / `post_python_file` reach Maya through `maya_launcher`'s
one-shot `UKORE_MAYA_AGENT_POST_MEL` (set in UkoreHub's environment around
the opener call, cleared after; see that plugin's README). maya_launcher
puts it **first** in Maya's `-command` chain (MEL aborts the chain at the
first error, so a failing scene open/tool hook can't skip it), and the
bridge wraps it: `post_mel` in `evalDeferred`, `post_python_file` in
`maya.utils.executeDeferred(exec(...))`, so it runs once the scene is open.

**A `post_python_file` should do its work directly, not defer again.**
Verified 2026-11-04 on AnimatorTeam (ETA020): a second `cmds.evalDeferred`
queued from inside the script never fired; something in that repo's tool
set keeps Maya's idle queue busy. MayaPublisher's GUI batch
(`batch_runner.run_in_gui`, `evalDeferred(lowestPriority=True)`) waits the
same way and may hang there too.

## Verified

2026-11-04, UkoreHub run from the dev checkout with Portal's env
(`UKOREHUB_CACHE_DIR`/`STORAGE_DIR`/`DATA_DIR` -> `C:\Tonmai\FileWorkspace\*`;
a bare `python launcher.py` falls back to `Documents\UkoreHub\*` and the
bridge writes its session file there instead): `ping`, `describe`,
`list_repos`, and `open_file` on AnimatorTeam's ETA020 with a
`post_python_file` that ran MayaPublisher's UnityShotFace and quit Maya.
`metadata.get_project`, `list_programs`, `file_opener_registry.find_opener`
and `program_launch_registry.find_launcher` exist as used.

## Client

jcoopy's `tools/ukorehub.py` (Merdera Project `jcoopy` repo):
`python tools/ukorehub.py <cmd> key=value ...`.
