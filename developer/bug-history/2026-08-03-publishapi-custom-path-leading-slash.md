# RigPublisher published into C:\<name> instead of the repo's Custom Path

## Symptom

User connected RigTeam's RigPublisher to a pipeline connection whose
Custom Path was stored as `/rig_publish`. Repository Setting correctly
showed "Currently publishing to: PublishToUnity — RigUnityPublish", but
the Maya-side Rig Publisher tool's "Publish Destination" showed
`C:\rig_publish` — the target repo's cloned folder was dropped entirely.

## Root cause

Same bug as
[2026-07-20-playblast-custom-path-leading-slash.md](2026-07-20-playblast-custom-path-leading-slash.md),
recurring in a file that entry's own "Lesson" said to grep for and missed:
`plugins/studio/PublishApi/maya-scripts/PublishApi/repo_paths.py`'s
`get_publish_root(tool_id)` joined the resolved target repo path and the
stored Custom Path with pathlib's `/` operator, unstripped:

```python
return str(target_repo_path / custom_path["path"])
```

`CustomPath.path` is raw, unsanitized user input — a leading `/` (as
typed here, `/rig_publish`) has its own root on Windows, so
`WindowsPath("D:/workspace/RigPublish") / "/rig_publish"` evaluates to
`WindowsPath("/rig_publish")`, which resolves to `C:\rig_publish` (the
current drive root) once stringified — the same silent drive-root anchor
`UkoreShotPlayblast`/`UkoreShot` hit in the earlier entry.
`get_publish_root` is consumed by every Publisher plugin
(`ModelPublisher`, `RigPublisher`, `AnimationPublisher`) via
`function.py`'s `publish(ticket)`, so this bug affected all three, not
just RigPublisher — it just happened to be RigPublisher's Custom Path that
had a leading slash first.

## Fix

`repo_paths.py`'s `get_publish_root` now strips leading separators before
joining, same one-liner as the earlier fix:

```python
return str(target_repo_path / custom_path["path"].lstrip("/\\"))
```

## Lesson

The earlier entry's lesson ("grep for `custom_path["path"]` before adding
a new consumer") wasn't followed when `PublishApi/repo_paths.py` was
written on 2026-07-19, one day before that lesson was written down — the
grep step only prevents *future* consumers, it doesn't retroactively catch
existing ones. After fixing this class of bug anywhere, actually run the
grep across the whole repo once (`custom_path\["path"\]` or
`custom_path\.path`) and check every hit, not just the file that prompted
the fix. As of this entry, one more unfixed instance remains (flagged, not
yet fixed — separate task):
`plugins/studio/UkoreBrowser/maya-scripts/UkoreBrowser/core/repo_context.py`
(`ref_path = ref_repo_path / custom_path["path"]`).
`plugins/studio/UkoreReferenceEditor/maya-scripts/UkoreReferenceEditor/core.py`
(`plugins/studio/ReferenceRedirector` at the time this entry was written,
renamed the same day) — `_connect_input_targets`'s
`targets.append(repo_path / custom_path["path"])` — was fixed the same day
this entry flagged it, to
`targets.append(repo_path / custom_path["path"].lstrip("/\\"))`.
