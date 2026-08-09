# 2026-08-09 — Switching to DebugConsole or BananaSketch crashed with `AttributeError: ... object has no attribute 'set_repo'`

## Symptom

Clicking the "Debug Console" sidebar row, or navigating to BananaSketch
(`cache/plugins/BananaSketch/`, via UkoreShot's Edit Comment button), crashed
the whole app with `AttributeError: 'DebugConsolePage' object has no
attribute 'set_repo'` / `'BananaSketchPage' object has no attribute
'set_repo'`, raised from `interface/main_window.py`'s
`_on_navigation_changed` -> `_apply_to_current_page`.

## Root cause

`interface/main_window.py`'s `_apply_to_current_page`/
`_apply_to_persistent_pages` called `page.set_repo(project, repo,
workspace_root)` unconditionally on whatever page was current, treating
`set_repo` as a mandatory interface every `SectionSpec.page_factory`-built
page must implement. It never was documented as mandatory in
`interface/section_registry.py`'s `SectionSpec`/`UICommandService` — pages with no
notion of "active repo" (`plugins/core/DebugConsole/debug_console_page.py`,
`cache/plugins/BananaSketch/interface/editor_page.py`) simply never
implemented it, and nothing surfaced that gap until a user actually switched
to one of those sections.

## Fix

Added `MainWindow._apply_set_repo(page)`, which looks up `set_repo` via
`getattr(page, "set_repo", None)` and only calls it if present/callable —
matching the same optional-protocol pattern `_navigate_and_focus` already
uses for `browse_to_path` (see the comment at
`interface/main_window.py`'s `_navigate_and_focus`). Both
`_apply_to_current_page` and `_apply_to_persistent_pages` now go through it
instead of calling `page.set_repo(...)` directly.

## Lesson

When `MainWindow` needs to reach into a plugin-supplied page for an
optional capability (repo-awareness, focus-a-path, etc.), treat it as a
protocol method checked with `getattr(...)`/`callable(...)`, never a method
called unconditionally — `SectionSpec.page_factory` accepts pages from any
plugin, including ones with no reason to care about the active repo. Before
adding a new unconditional `page.<method>(...)` call in `main_window.py`,
check whether every current page (including `plugins/core/DebugConsole/`
and any `cache/plugins/*` repo plugin) actually implements it; if not, guard
it the way `_navigate_and_focus` already does for `browse_to_path`.
