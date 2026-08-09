# developer/

Dev-only tooling and docs, grouped together so they can be stripped as one
unit when publishing to the release repo's `main`. Lives only in this repo
(`UkoreHubDev`, remote `origin`) - the published `main` on the separate
`UkoreHubRelease` repo never has a `developer/` folder (nor `.claude/`),
only the plain app code artists actually run.

`UkoreHub.exe` itself (and the admin tooling that builds it) used to live
here too, under `packaging/` - it moved out into its own separate repo,
[`UkoreHubLauncher`](https://github.com/tonmaiart/UkoreHubLauncher), so an
ordinary app release can never again try to overwrite the exe file that's
busy running it. See
[`bug-history/2026-08-08-self-update-locked-own-exe.md`](bug-history/2026-08-08-self-update-locked-own-exe.md)
and that repo's own README.md.

- `tests/` - pytest suite (`pytest.ini` at repo root points `testpaths` here).
- [`bug-history/`](bug-history/README.md) - record of real bugs fixed in
  this codebase, with reusable "Lesson" entries.
- [`GLOSSARY.md`](GLOSSARY.md) - maps casual/colloquial terms used in this
  project onto their actual feature/file.
- `commit-main.ps1` - publishes this repo's current `main` onto the
  `UkoreHubRelease` repo's `main`, stripping `.claude/` and `developer/`
  itself in the process. See below.

Because the release repo's `main` never has a `developer/` folder,
publishing also drops the `tests/` suite - it only exists here, in
UkoreHubDev. `build/` never ships either way (gitignored).

## Repo split

Three separate GitHub repos, not branches of one repo:
- **`UkoreHubDev`** (this repo, remote `origin`) - all day-to-day work
  (features, fixes, edits, `.claude/` skills, this folder) happens directly
  on its `main` branch. There is no `dev` branch here - this repo's `main`
  *is* the working branch, unrelated to (and never pushed directly to) the
  other repos' `main` below.
- **`UkoreHubRelease`** (remote `release`, added automatically by
  `commit-main.ps1` if missing; GitHub repo name is `UkoreHub`) - holds
  only `main`, a clean mirror of this repo's `main` minus the folders
  above. This is the app repo artists actually clone/pull from - see the
  nested `app/` clone described in
  [`UkoreHubLauncher`](https://github.com/tonmaiart/UkoreHubLauncher)'s
  README.md.
- **`UkoreHubLauncher`** - a wholly separate repo (not published to via
  `commit-main.ps1` or anything else here) holding `UkoreHub.exe` and the
  admin tooling that builds it. Edited directly in its own local clone,
  outside this repo entirely. See its own README.md for why it's split out
  and how the two repos relate on an artist's machine.

To publish this repo's current state to `UkoreHubRelease`'s `main`:

```powershell
developer/commit-main.ps1
```

Requirements:
- Must be run from this repo's `main` branch.
- The working tree must be clean (commit or stash first) - the script
  refuses to run otherwise, so it never syncs uncommitted work.

What it does: fetches the `release` remote (`UkoreHubRelease`) and checks
its `main` out into a temporary `git worktree` on a throwaway local branch
(`release-sync`) - or starts an orphan branch if `release/main` doesn't
exist yet - replaces its tracked files with this repo's current `main`
tree, deletes `.claude/` and `developer/` from that copy, commits the
result, and **pushes `release-sync` to `release/main`** - all without
touching your working directory or switching your current branch. If the
push fails (network, diverged remote, etc.) the commit still lands locally
on `release-sync`; the script warns you to push manually once resolved.

Pass `-Message "..."` to use a custom commit message instead of the
default (which references the commit being synced). Pass `-NoPush` to
commit to the local `release-sync` branch only and push it yourself later.

### Shortcut: `git commit-release`

The `-ExecutionPolicy Bypass -File ...` invocation below is wordy enough
that it's worth a git alias instead. This is a per-machine setting stored
in `.git/config`, not tracked by the repo, so each dev who wants the
shortcut runs this once:

```bash
git config alias.commit-release '!powershell -ExecutionPolicy Bypass -File "$(git rev-parse --show-toplevel)/developer/commit-main.ps1"'
```

After that, `git commit-release` (from anywhere inside the repo, Git Bash
or PowerShell) does the same thing as the invocation below - and extra
args pass straight through, e.g. `git commit-release -NoPush` or
`git commit-release -Message "..."`.

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
