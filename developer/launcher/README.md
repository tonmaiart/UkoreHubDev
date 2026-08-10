# developer/launcher/

`UkoreHubLauncher.exe`'s own source and dev docs. The exe itself lives at
the repo root (`../../UkoreHubLauncher.exe`, git-tracked deliberately, not
gitignored) — this folder holds everything that builds it, plus its own
`bug-history/`. Never published (see [`../README.md`](../README.md) for
the publish mechanics) — artists only ever get the committed `.exe`, not
this source.

Used to be its own separate dev repo, `UkoreHubLauncherDev`, publishing to
a separate `UkoreHubLauncher` release repo — merged into this repo (as
this folder) so there's one dev repo instead of two. The release side is
unchanged: `UkoreHubLauncher` (remote `release-launcher`) still holds only
the exe, published via `git release-launcher` (see `../README.md`).

- [`launcher_build/`](launcher_build/) — all the build-time source:
  - `exe_entry.py` — the tiny script PyInstaller compiles into
    `UkoreHubLauncher.exe`. Hands off to `updater.py`'s `main()`.
  - `updater.py` — the actual pre-launch logic: git/Python prerequisite
    checks, self-update of the launcher (skipped in dev mode — see below),
    bootstrap/update of `app/` (also skipped in dev mode), GitHub
    device-flow login (tkinter UI), then spawns `../../app/launcher.py`.
    See its own module docstring for the full breakdown, including why
    `core/exceptions.py`/`core/models.py`/`core/paths.py`/`core/theme.py`/
    `core/store.py`/`core/github/` here are **vendored copies** of
    `../../app/core/`'s identically-named files rather than an import — a
    change to the real ones (OAuth flow, token storage, config schema)
    needs to be manually mirrored here too if it should also apply to this
    pre-launch login screen.
  - `build_exe.py` — admin-only: run this (or `git release-launcher`, which
    calls it automatically) to rebuild `UkoreHubLauncher.exe` at the repo
    root after rebranding `icon.ico` or changing `exe_entry.py`/
    `updater.py` themselves. Installs `pyinstaller`/`keyring` into the
    current environment if missing. `--icon`/`--name` CLI args, defaults to
    `icon.ico`/"UkoreHubLauncher".
  - `icon.ico` — the icon baked into `UkoreHubLauncher.exe`. Swap this file
    and rerun `build_exe.py` to rebrand.
  - `r2_credentials.example.py` — tracked template for the real,
    **gitignored** `r2_credentials.py` sibling module `updater.py` imports
    to bake the studio's shared Cloudflare R2 key into the exe (see the
    `ukorehub-cloud-sync` skill). Copy the example, fill in the four real
    values (rotate them first if they were ever exposed insecurely), then
    run `build_exe.py`/`git release-launcher` as usual — no other build
    step needed, it bundles the same way `updater.py` itself does.
    Skipping this file entirely is fine for ordinary dev-mode testing;
    the built exe just launches with cloud sync disabled.
- `build/` — PyInstaller's intermediates (gitignored, regenerated every
  build) — kept here rather than at the repo root so it stays grouped with
  the rest of this dev-only folder.
- [`bug-history/`](bug-history/README.md) — record of real bugs fixed in
  this launcher tooling. Read before changing code in an area that already
  has an entry.

For `app/`'s own dev-only docs/tests, see [`../app/`](../app/README.md)
instead — a launcher-side task never touches `../../app/` or `../app/`,
and vice versa (see root `CLAUDE.md`'s "Scoped editing" section).

## Dev mode — testing against this repo's own `app/`

Because `UkoreHubLauncher.exe` at the repo root and `../../app/` now live
in the *same* git working tree (this dev repo), running the exe from here
would be dangerous if it did what it does in a real install: self-update
this repo's own git state, and treat `app/` as an independent clone to
`git init`/hard-reset against the `UkoreHub` release repo — either would
blow away local dev work.

`updater.py`'s `_is_dev_checkout` detects this (a `developer/` folder next
to the running exe — never present in a real artist install, since it's
never published) and skips both self-update steps entirely when true,
using `../../app/` as-is instead. Everything else — prerequisite checks,
GitHub login, the first-run workspace-folder picker, spawning
`app/launcher.py` — runs exactly as it would for a real user, so
double-clicking `UkoreHubLauncher.exe` here is a real way to exercise that
whole flow against your local `app/` edits.

**Rebuild after changing anything under `launcher_build/`** — PyInstaller
bakes the source into the binary, so editing `updater.py` alone doesn't
change what double-clicking the exe does until it's rebuilt:

```bash
python developer/launcher/launcher_build/build_exe.py
```

## Layout on a real artist install

(Unchanged by the dev-repo merge — this only describes what an install
built from the two release repos looks like, not this dev repo.)

```
UkoreHubLauncher.exe        <- from the UkoreHubLauncher release repo, self-updates rarely
app/                <- clone of the UkoreHub release repo, gitignored here,
                        bootstrapped/updated on every launch
  launcher.py
  core/  interface/  plugins/  data/  cache/  storage/  ...
```

Double-click `UkoreHubLauncher.exe` — it brings itself up to date first
(rare — only when an admin rebuilds/republishes it), then bootstraps or
updates the nested `app/` clone (frequent — every ordinary app release),
then checks Python/git-lfs, handles GitHub login, and spawns
`app/launcher.py`.
