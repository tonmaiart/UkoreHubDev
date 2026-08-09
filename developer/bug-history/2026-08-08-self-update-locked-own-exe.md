# UkoreHub.exe self-update failed: "unable to unlink old 'UkoreHub.exe'"

## Symptom

On launch, `UkoreHub.exe` showed:

```
UkoreHub update failed:
git checkout -f -B main --track origin/main failed: error: unable to
unlink old 'UkoreHub.exe': Invalid argument
Switched to a new branch 'main'

You can continue with the current version — restart to retry.
```

Restarting sometimes "fixed" it, sometimes didn't — looked flaky/random.

## Root cause

`developer/packaging/updater.py`'s `ensure_up_to_date` (called from
`UkoreHub.exe` itself, before it hands off to `launcher.py`) runs
`git checkout`/`git pull` against the repo root to self-update. `UkoreHub.exe`
is git-tracked and deliberately **not** gitignored (see
`developer/packaging/README.md` — it's a shared studio-wide binary rebuilt
and recommitted on every release, same pattern as `data/thumbnails/`).

So any release that changes `UkoreHub.exe`'s bytes makes git try to
unlink/overwrite the working-tree copy of `UkoreHub.exe` — which is the
exact file currently mapped into memory and executing this code. Windows
(unlike Linux, where `unlink` on an open file just works) refuses to
delete or overwrite a file that's currently executing, and git reports
that OS-level refusal as `unable to unlink old 'UkoreHub.exe': Invalid
argument`. This wasn't specific to the fresh-bootstrap path (`git init` +
force `checkout` for a plain ZIP extract) — an ordinary already-cloned
install's `git pull` could hit the identical failure on any release that
touched the exe, which is why it looked intermittent rather than
consistently reproducible.

## Fix

`developer/packaging/updater.py`: added `_relocate_self_exe`, a context
manager wrapping the whole body of `ensure_up_to_date`. Before any git
operation, if this process **is** the `UkoreHub.exe` at `repo_root`
(checked via `sys.frozen` + `sys.executable`), it renames that exe aside
to `UkoreHub.exe.old-<pid>`. Windows allows renaming a running/locked exe
even though it disallows deleting or overwriting it in place — the same
trick self-updating browsers use, since a running process keeps its open
file handle regardless of what the directory entry is called afterward.
With the path clear, `git checkout`/`git pull` can write a fresh
`UkoreHub.exe` unobstructed. The renamed-aside copy is deleted on success,
or moved back into place on failure so the "continue with the current
version" message in the error dialog stays true. A leftover
`UkoreHub.exe.old-*` from a previous interrupted run (e.g. the process was
killed mid-update) is swept on the next launch. `.gitignore` got a
`/UkoreHub.exe.old-*` entry so a leftover never gets accidentally staged.

## Lesson

Any file that is both **git-tracked** and **the currently-executing
binary** (or otherwise open/locked by the very process doing the git
operation) will make `git checkout`/`git pull` fail to unlink it on
Windows — this is an OS file-locking rule, not a git bug, and it isn't
limited to a "fresh install" edge case; it recurs on every ordinary update
that changes that file's tracked bytes. If a future change adds another
self-contained/frozen entry point that's also committed into the repo it
updates itself from, it needs the same rename-aside treatment before the
git operation, not just a `-f` force-checkout retry (force-checkout still
hits the same unlink call and fails the same way).

## Update (2026-08-09): root cause removed for the frequent case

The rename-aside fix above still works and is still needed, but only for
a now-rare case. `UkoreHub.exe` moved out of this repo entirely into its
own repo, [`UkoreHubLauncher`](https://github.com/tonmaiart/UkoreHubLauncher)
— see `developer/README.md`'s "Repo split" section. Artists now get
`UkoreHub.exe` in an outer folder with a nested `app/` clone of this repo
inside it; the exe self-updates its own (rarely-changing) repo with
`_relocate_self_exe` still wrapping that pull, but the frequent case —
an ordinary app-code release touching `app/` — never contains
`UkoreHub.exe` at all, so it structurally cannot hit this bug anymore.
Existing single-folder installs (exe and app code in the same folder) are
not auto-migrated; artists reinstall by hand into the new layout.
