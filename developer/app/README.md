# developer/app/

Dev-only docs and tests for [`../../app/`](../../app/README.md) (the actual
UkoreHub tool). Lives only in this dev repo — never published (see
[`../README.md`](../README.md) for the publish mechanics and why this
folder is automatically excluded, not exclude-listed).

- [`GLOSSARY.md`](GLOSSARY.md) — maps casual/colloquial terms used in this
  project onto their actual feature/file. Read before acting on one, or
  before asking a clarifying question about one — see root `CLAUDE.md`.
- [`bug-history/`](bug-history/README.md) — record of real bugs fixed in
  `app/`, with reusable "Lesson" entries. Read before changing code in an
  area that already has an entry.
- `tests/` — pytest suite. `pytest.ini` at the repo root points
  `testpaths` here and sets `pythonpath = app`, so these tests' existing
  `from core...`/`from interface...` imports resolve against `../../app/`
  without any per-file path changes.

For `UkoreHubLauncher.exe`'s own dev-only docs/source, see
[`../launcher/`](../launcher/README.md) instead — a launcher-side task
never touches this folder, and vice versa (see root `CLAUDE.md`'s "Scoped
editing" section).
