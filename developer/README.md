# developer/

Dev-only tooling and docs, grouped together so they can be stripped as one
unit when publishing to `main`. Lives only on the `dev` branch - `main`
never has a `developer/` folder (nor `.claude/`), only the plain app code
artists actually run.

- [`packaging/`](packaging/README.md) - admin-only tooling to build
  `UkoreHub.exe`.
- [`bug-history/`](bug-history/README.md) - record of real bugs fixed in
  this codebase, with reusable "Lesson" entries.
- [`GLOSSARY.md`](GLOSSARY.md) - maps casual/colloquial terms used in this
  project onto their actual feature/file.
- `commit-main.ps1` - publishes the current `dev` branch onto `main`,
  stripping `.claude/` and `developer/` itself in the process. See below.

## Branch workflow

All day-to-day work (features, fixes, edits, `.claude/` skills, this
folder) happens on `dev`. `main` is kept as a clean mirror of `dev` minus
the folders above - the branch artists actually clone/pull from.

To publish `dev`'s current state to `main`:

```powershell
developer/commit-main.ps1
```

Requirements:
- Must be run from the `dev` branch.
- `dev`'s working tree must be clean (commit or stash first) - the script
  refuses to run otherwise, so it never syncs uncommitted work.

What it does: checks out `main` into a temporary `git worktree`, replaces
its tracked files with `dev`'s current tree, deletes `.claude/` and
`developer/` from that copy, and commits the result to `main` - all
without touching your `dev` working directory or switching your current
branch. It does **not** push; review the result (`git log main`,
`git show main`) and run `git push origin main` yourself when ready.

Pass `-Message "..."` to use a custom commit message instead of the
default (which references the `dev` commit being synced).
