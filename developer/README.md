# developer/

Dev-only tooling and docs, grouped together so it's automatically excluded
from both release publishes (see below) without an exclude-list — neither
release repo's `main` ever has a `developer/` folder (nor `.claude/`).
Split into two folders:

- [`app/`](app/README.md) — dev docs/tests for the actual app (`../app/`):
  `GLOSSARY.md`, `bug-history/`, `tests/`.
- [`launcher/`](launcher/README.md) — `UkoreHubLauncher.exe`'s own source
  (`launcher_build/`) and its `bug-history/`.

Plus two scripts, right here (repo-wide tooling, not specific to either
side):

- `release_app.ps1` — publishes `../app/`'s contents to the `UkoreHub`
  release repo.
- `release_launcher.ps1` — rebuilds the exe, then publishes it to the
  `UkoreHubLauncher` release repo.

## Repo split

One dev repo, two release repos:
- **`UkoreHubDev`** (this repo, remote `origin`) — all day-to-day work
  (app features/fixes, launcher changes, `.claude/` skills, this folder)
  happens directly on its `main` branch. There is no `dev` branch here —
  this repo's `main` *is* the working branch, unrelated to (and never
  pushed directly to) the release repos' `main` below. Used to be two
  separate dev repos (`UkoreHubDev` for the app, `UkoreHubLauncherDev` for
  the launcher exe) — merged into this one so there's a single place to
  work; the old `UkoreHubLauncherDev` repo still exists as an untouched
  archive of its own history but nothing is edited there anymore.
- **`UkoreHub`** (remote `release`, added automatically by
  `release_app.ps1` if missing) — holds only `main`, a clean mirror of
  this repo's `../app/` contents (flattened up to its own root). This is
  the app repo artists actually clone/pull from — see the nested `app/`
  clone described in `../developer/launcher/README.md`.
- **`UkoreHubLauncher`** (remote `release-launcher`, added automatically by
  `release_launcher.ps1` if missing) — holds only the tracked
  `UkoreHubLauncher.exe` at its root. Artists' installs self-update from
  here (rare — only when an admin rebuilds/republishes it).

## Publishing: `release_app.ps1`

```powershell
git release-app
git release-app -Message "Add cloud data admin plugin"
git release-app -NoRelease   # origin/main only, skip the release-repo publish
```

Must be run from `main`. Stages everything (`git add -A`) across the whole
repo, commits, and pushes to **this repo's own** `origin/main` in one shot,
no confirmation prompt — then publishes that same state to `UkoreHub` too:
fetches `release`, checks its `main` out into a temporary `git worktree`
(or starts an orphan branch if it doesn't exist yet), replaces its tracked
files with `../app/`'s contents (checked out from this repo's `main`,
then flattened up to the worktree root so the release repo's root looks
like a plain checkout — see `release_app.ps1`'s own comments for the
hidden-file-safety details), commits, and pushes. Never uses `--force` or
`--no-verify` on either push — a rejected push or a failing pre-commit hook
stops the script and reports the git error rather than working around it.
If nothing's changed locally, it skips straight to the release-repo
publish step (still useful if a previous run's release publish failed but
the origin push already succeeded) instead of creating an empty commit.
Omitting `-Message` falls back to a timestamped "Fast commit: ..." message
for the origin commit — fine for WIP, but prefer a real message when the
change is worth describing for later; the release-repo publish always uses
its own "Sync from main @ &lt;hash&gt;: ..." message regardless.

## Publishing: `release_launcher.ps1`

```powershell
git release-launcher
git release-launcher -Message "Rebuild: v1.2.0 icon refresh"
git release-launcher -NoRelease
```

Must be run from `main`. Same shape as `release_app.ps1`, with two
differences: it rebuilds `UkoreHubLauncher.exe`
(`developer/launcher/launcher_build/build_exe.py`) *before* staging
anything — a failed build stops the script, nothing gets committed — and a
rejected push **force-pushes** instead of stopping to reconcile, on both
the `origin` push and the release-repo push (local is always authoritative
here — a plain `git pull`/merge between these repos can fail hard with
"refusing to merge unrelated histories" with no one watching to reconcile
it; see
`developer/launcher/bug-history/2026-08-09-fast-commit-push-rejected-unrelated-histories.md`).
The release-repo publish checks out only the tracked `UkoreHubLauncher.exe`
file (no flatten step needed — the release repo's root only ever holds
that one file).

## Git aliases: `git release-app` / `git release-launcher`

Per-machine settings stored in `.git/config`, not tracked by the repo —
each dev who wants the shortcut runs these once:

```bash
git config alias.release-app '!powershell -ExecutionPolicy Bypass -File "$(git rev-parse --show-toplevel)/developer/release_app.ps1"'
git config alias.release-launcher '!powershell -ExecutionPolicy Bypass -File "$(git rev-parse --show-toplevel)/developer/release_launcher.ps1"'
```

After that, `git release-app` / `git release-launcher` (from anywhere
inside the repo, Git Bash or PowerShell) do the same thing as the
invocations above — extra args pass straight through, e.g.
`git release-app -NoRelease` or `git release-launcher -Message "..."`.

### Running the scripts directly from Git Bash / MINGW64

`.ps1` files aren't shell scripts — running `developer/release_app.ps1`
directly from Git Bash tries to execute it as bash and fails with a
`syntax error near unexpected token` on the `<#` comment block. Invoke
PowerShell explicitly instead:

```bash
powershell -File developer/release_app.ps1
```

From an actual PowerShell window, `.\developer\release_app.ps1` works
directly — no need for `powershell -File`.

### "running scripts is disabled on this system"

Windows PowerShell's default execution policy blocks all `.ps1` scripts,
signed or not. Two ways around it:

- One-off, no permanent change (recommended):
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\developer\release_app.ps1
  ```
- Permanent, for this Windows user account — changes a machine security
  setting, so run it yourself rather than scripting it:
  ```powershell
  Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
  ```
  After this, plain `.\developer\release_app.ps1` works every time.
