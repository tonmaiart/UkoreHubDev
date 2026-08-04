# developer/

Dev-only tooling and docs, grouped together so they can be stripped as one
unit when publishing to `main`. Lives only on the `dev` branch - `main`
never has a `developer/` folder (nor `.claude/`), only the plain app code
artists actually run.

- [`packaging/`](packaging/README.md) - admin-only tooling to build
  `UkoreHub.exe`.
- `build/` - PyInstaller intermediates from `packaging/build_exe.py`,
  gitignored, regenerated every build.
- `tests/` - pytest suite (`pytest.ini` at repo root points `testpaths` here).
- [`bug-history/`](bug-history/README.md) - record of real bugs fixed in
  this codebase, with reusable "Lesson" entries.
- [`GLOSSARY.md`](GLOSSARY.md) - maps casual/colloquial terms used in this
  project onto their actual feature/file.
- `commit-main.ps1` - publishes the current `dev` branch onto `main`,
  stripping `.claude/` and `developer/` itself in the process. See below.

Because `main` never has a `developer/` folder, publishing also drops the
`tests/` suite from `main` - it only exists on `dev`. `build/` never ships
either way (gitignored).

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
`developer/` from that copy, commits the result to `main`, and **pushes
`main` to `origin`** - all without touching your `dev` working directory
or switching your current branch. If the push fails (network, diverged
remote, etc.) the commit still lands locally; the script warns you to
push manually once resolved.

Pass `-Message "..."` to use a custom commit message instead of the
default (which references the `dev` commit being synced). Pass `-NoPush`
to commit to local main only and push it yourself later.

### Running it from Git Bash / MINGW64

`.ps1` files aren't shell scripts - running `developer/commit-main.ps1`
directly from Git Bash tries to execute it as bash and fails with a
`syntax error near unexpected token` on the `<#` comment block. Invoke
PowerShell explicitly instead:

```bash
powershell -File developer/commit-main.ps1
```

From an actual PowerShell window, `.\developer\commit-main.ps1` works
directly - no need for `powershell -File`.

Also, when pasting a failing command's output back into a terminal for a
retry, paste only the command itself, not the whole block including old
error text or shell prompts (e.g. a stray `tomatactics@... (dev)` line) -
PowerShell will try to run every pasted line as its own command.

### "running scripts is disabled on this system"

Windows PowerShell's default execution policy blocks all `.ps1` scripts,
signed or not. Two ways around it:

- One-off, no permanent change (recommended):
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\developer\commit-main.ps1
  ```
- Permanent, for this Windows user account - changes a machine security
  setting, so run it yourself rather than scripting it:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
  After this, plain `.\developer\commit-main.ps1` works every time.
