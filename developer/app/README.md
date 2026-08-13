# developer/app/

Dev-only docs and tests for [`../../app/`](../../app/README.md) (the actual
UkoreHub tool). Lives only in this dev repo — never published (see
[`../README.md`](../README.md) for the publish mechanics and why this
folder is automatically excluded, not exclude-listed).

- [`GLOSSARY.md`](GLOSSARY.md) — maps casual/colloquial terms used in this
  project onto their actual feature/file. Optional reference, not a
  mandatory read — consult it if a casual term is genuinely ambiguous.
- [`docs/`](docs/README.md) — reference docs for `app/` subsystems dense
  enough to warrant a standalone doc, e.g.
  [`docs/plugin-api.md`](docs/plugin-api.md) for `app/plugin_api/`. Read
  before opening the source folder a doc here covers.
- `tests/` — pytest suite. `pytest.ini` at the repo root points
  `testpaths` here and sets `pythonpath = app`, so these tests' existing
  `from core...`/`from interface...` imports resolve against `../../app/`
  without any per-file path changes.
- `check_import_boundaries.py` — standalone script (no lint/pre-commit
  infra exists in this repo) enforcing `app/`'s layering rules: `plugins/`
  never imports `core.*` directly (go through `plugin_api` instead),
  `core/` never imports outward, `plugin_api/` never imports
  `interface.*`/`plugins.*`. Run by hand after touching `app/core/`,
  `app/interface/`, `app/plugins/`, or `app/plugin_api/`:
  `python developer/app/check_import_boundaries.py`. Not wired into CI or
  a git hook — a manual gate only.

For `UkoreHubLauncher.exe`'s own dev-only docs/source, see
[`../launcher/`](../launcher/README.md) instead — a launcher-side task
never touches this folder, and vice versa (see root `CLAUDE.md`'s "Scoped
editing" section).
