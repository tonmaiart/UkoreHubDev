# GLOSSARY.md

Casual/colloquial terms used when talking about UkoreHub, mapped to the
actual feature or file each one refers to. Added 2026-07-20 after "ปุ่ม
setting ของ program" (meaning the app's own Setting button) got misread as
the Program Database feature — consult this before assuming a casual term
matches the nearest-sounding code symbol or feature name; several terms
below are easy to misread that way.

## "The program" / "program's setting"

When used casually (e.g. "ปุ่ม setting ของ program"), "program" usually
means **UkoreHub itself**, not the Program Database feature below. "The
program's Setting button" = the app-level **Setting** popup, opened via
the icon-only Setting button in Sidebar's footer
(`interface/sidebar/sidebar.py`'s `setting_button`, positioned right after
the GitHub username/avatar). Wired through
`MainWindow._on_settings_requested` -> `interface/settings/settings_view.py`'s
`SettingsDialog`.

**Not to be confused with:**

- **Program Database** — Settings > Developer > "Program Database", a CRUD
  list of pipeline software (Maya, Nuke, ...) a repo can declare as a
  requirement (`core/program_store.py`,
  `interface/settings/program_database_page.py`). "Program" here means one
  catalog entry, not the app.
- **Repository Setting** — the phrase used for *per-repo* settings, opened
  from Project Editor's node right-click menu ("Repository Setting...").
  Not a popup of its own anymore — it opens the same app-level Setting
  dialog (`interface/settings/settings_view.py`'s `SettingsDialog`),
  landing on its **Repo Setting (Dev)** top tab, which groups tabs under
  two headers — "Repository" (Local Repository, Custom Paths, Enable
  Plugin) and "Plugins" (every plugin-contributed `CATEGORY_REPO`
  tab). Before this refactor (2026-07-15 through 2026-08-09) it was its
  own popup (`plugins/core/project_editor/repo_settings_panel.py`,
  retired) to avoid duplicating these tabs in both Settings and here — the
  same reasoning now argues for one dialog instead of one popup, since
  both ever only rendered the same `SettingsTabRegistry` entries.

## "UkoreBrowser" vs. "Browser Links" (removed)

Added 2026-08-10 after "ลบ UkoreBrowser Plugin" got taken literally and
removed the wrong one of these two similarly-named, completely unrelated
things — always ask which one is meant if a request just says "Browser"
without one of the fuller names below:

- **`UkoreBrowser`** — a Maya-side asset-browser **plugin**, launched from
  inside Maya (Ukore Studio Tool menu's "Ukore File Browser..." item, plus
  an auto-launch hook), not a UkoreHub UI panel. Was bundled at
  `plugins/repo_internal/UkoreBrowser/`; as of 2026-08-10 (once every
  `repo_internal` plugin moved out to its own GitHub repo)
  it's its own separate git clone under `cache/plugins/UkoreBrowser/`
  instead, same move `UkoreShot`/`MayaNgSkin` made earlier. See its own
  README. Opt-in per repo like any other `cache/plugins/` plugin. **Still
  exists** — kept after this same-day mix-up.
- **Browser Links** (a.k.a. the old **"Browser"** tab in Repository
  Setting's "Repository" group) — an unrelated core UkoreHub feature that
  used to exist: per-repo custom URL shortcuts (`core/models.py`'s old
  `BrowserLink`, `Repo.browser_links`) rendered as dynamic Sidebar rows,
  opening in the OS's default browser on click. **Removed entirely
  2026-08-10** (the same day as the mix-up above, once it turned out this
  one — not `UkoreBrowser` — was the actual removal target) — no longer a
  feature, no Settings tab, no `BrowserLink` model, no dynamic Sidebar row
  mechanism (`SectionTabList.add_dynamic_tab`/`clear_dynamic_tabs` were
  removed with it). If asked about it: it no longer exists; see git history
  around this date if it needs to come back. Was never Maya-related and
  was never a plugin, despite the name collision with `UkoreBrowser` above.

## "Viewgraph"

Not a name used anywhere in the codebase itself — refers to Project
Editor's node-graph view: the `QGraphicsView` showing every repo in a
project as a node, with pipeline connections drawn as edges between them.
Code name: `ProjectGraphView`
(`plugins/core/project_editor/project_graph_view.py`), hosted inside
`ProjectEditorPage`. An ordinary Sidebar row/`view_stack` page like every
other section — before this refactor it was always visible, docked beside
whichever section was currently showing (`SectionSpec.persistent=True`,
now removed).

## Custom Path — "Input" vs "Output"

Two related-but-distinct things both get called "Custom Path", and the
in-app button labels don't map cleanly onto "Input"/"Output" the way
you'd expect:

- **A repo's own declared Custom Path(s)** — named locations *within*
  that repo that other repos can point at (`pipeline_store.py`'s
  `CustomPath`). Managed under Repository Setting > Custom Paths >
  **"Create Input Path"** — despite the button's name, these are the
  locations this repo *exposes* for others to connect to, not something
  it consumes.
- **A pipeline connection** — this repo pointing at *another* repo's
  declared Custom Path (`pipeline_store.py`'s `RepoRef`, list returned by
  `PipelineStore.get_inputs`). Managed under Repository Setting > Custom
  Paths > **"Connect Input Path"**. Each connection carries its own
  `direction` field ("input" or "output", purely cosmetic — only affects
  which end of the drawn graph edge gets the arrowhead), and this is the
  actual "Input"/"Output" split shown in the Viewgraph's bottom-right
  overlay HUD (`ProjectGraphView._refresh_overlay`).

## Plugin vs Program

Already documented in root `CLAUDE.md`'s "Project layout" section — see
that instead of re-deriving from context: **Plugins** (`plugins/`) are
UkoreHub's own always-on sub-systems; a **Program** (`core/program_store.py`)
is a different concept entirely — it's a catalog entry for external
pipeline software (Maya, Nuke, ...) a repo can require.

## Ukore Reference Editor: "project" (e.g. "KafkaProj") means Repo, not Project

Added 2026-08-03 after `plugins/core/UkoreReferenceEditor` (built this
same session as `ReferenceRedirector`, renamed later the same day) got this
wrong twice in a row — first not matching it at all, then matching it
but comparing at the wrong granularity. When talking about an old broken
Maya reference's absolute Google-Drive path (e.g.
`G:\My Drive\Projects\KafkaProj\publish\...`), the studio's old colloquial
"project" (here, "KafkaProj") is the *client/show's own body of work* —
that maps onto a UkoreHub **`Repo`** (`core/models.py`), specifically its
`local_path`'s on-disk folder name (which never gets recomputed after a
rename — see the `ukorehub-core` skill's `resolve_repo_path` note — so a
repo renamed since the old Drive-path days, e.g. `KafkaProj` ->
`AnimatorTeam`, still has the old name baked into that folder). It does
**not** map onto a UkoreHub **`Project`** (`core/models.py`'s `Project`,
the umbrella that bundles several unrelated repos together, e.g.
"MerderaProject" containing both `RigTeam` and `AnimatorTeam`) — two repos
under the same UkoreHub Project are still a different old-style "project"
from each other. Any Internal/External-style classification of a reference
path against "the currently active project" has to compare **repo
identity**, not Project identity — see
`plugins/core/UkoreReferenceEditor/matcher.py`'s `find_match_for_path`
(repo-first matching) and `core.py`'s `_build_ref_entry`/`_build_texture_entry`
(via `_classify_path`, `matched_repo.id == active_repo.id`).

## "Program Launcher"

As of 2026-08-10, this is `plugins/core/software_linker/`'s sidebar tab
(`SoftwareLinkerPage`, label "Program Launcher") — **not** a plugin folder
named `program_launcher`. There used to be a separate
`plugins/core/program_launcher/` plugin with exactly that name (a
repo-scoped card grid, `Repo.required_program_ids` only, double-click to
launch, "Software Linker Setting" button jumping to a separate Settings >
Software Linker tab); it was retired the same day and its double-click
launch + `ProgramLaunchRegistry` wiring folded into `software_linker`,
which also absorbed the sidebar tab slot (order 40) and the "Program
Launcher" label itself. The old Settings > Software Linker tab is gone
too — linking now happens directly on this same sidebar tab. If asked to
"fix Program Launcher" or find `plugins/core/program_launcher/`, it means
`plugins/core/software_linker/plugin.py`'s `SoftwareLinkerPage` — see that
plugin's own README.md for the current shape (project-scoped, not
repo-scoped, unlike the retired version).

## Repo About (removed)

Referenced in old conversations as "About tab" or (mistakenly) "Plug-ins
about" — a per-repo info page (`interface/about/repo_about_page.py`,
"About" + "Requirement" sub-tabs) removed entirely 2026-07-20, no longer
needed. If asked about it: it no longer exists.

**Editing an existing repo's required Programs** (the old
"Requirement" sub-tab's job) got a real replacement 2026-07-29, now living
at Settings > Repo > **Requirements & Plugins** (`interface/repo_settings/
requirements_and_plugins_page.py`, merged there 2026-08-04 from its
original standalone tab) — hosts the same `RequirementsTreeWidget` the
Add-Repo dialog uses, self-persisting on every check-state change — no
Save button, same convention as Enable Plugin/Custom Paths. Includes the
per-version pin picker for a multi-version Program (e.g. choosing 2024 vs
2026 for "Autodesk Maya" — see `core/models.py`'s `Repo.program_version_pins`
and `plugins/repo_internal/maya_launcher/link_resolution.py`). As of
2026-08-09, Program Database (and the `Program` catalog entries themselves)
is scoped per-Project, not studio-wide — see `core/models.py`'s
`Project.programs`.
