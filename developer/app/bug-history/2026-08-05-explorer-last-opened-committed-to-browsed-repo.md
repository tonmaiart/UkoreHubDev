# 2026-08-05 — Explorer's Last Opened Files list got committed into browsed repos

## Symptom

Studio repos browsed via Explorer sometimes ended up with a
`.ukorehub/explorer_last_opened_<username>.json` file staged/committed
into their own history, even though it's purely a personal, per-artist
working list with no relevance to anyone else's clone.

## Root cause

`plugins/core/explorer/last_opened_store.py`'s `LastOpenedStore` wrote its
JSON to `<browsed_repo_root>/.ukorehub/explorer_last_opened_<username>.json`
— inside whatever production repo the user had open in Explorer, not
inside UkoreHub's own repo. Keeping it out of that repo's git history
depended entirely on that repo's own `.gitignore` excluding `.ukorehub/`;
several studio repos never added that rule, so the file showed up as an
untracked/staged file in Submit like any other real change.

## Fix

`LastOpenedStore` now persists to this app's own
`<UkoreHub_root>/cache/explorer/last_opened_<repo_id>_<username>.json`
instead — `cache/` is wholesale gitignored in UkoreHub's own `.gitignore`
(same directory `cache/plugins/` repo plugins already live under), so the
file never touches a browsed repo's working tree or git status at all.
`LastOpenedStore.__init__` and `RepoBrowserWidget.set_root()` both gained
a required `repo_id` parameter (from `Repo.id`) to key the cache file per
repo, since the same UkoreHub-side folder now holds the list for every
repo instead of one file living inside each repo individually.

## Lesson

A per-user/per-machine cache file for data *browsed via* UkoreHub should
live under UkoreHub's own gitignored `cache/`, not inside the target
repo's working tree — writing into a production repo's tree makes that
repo's `.gitignore` a silent dependency for a feature that repo's owners
have no reason to know exists. If a future feature wants a similar "local
scratch state tied to a specific repo" cache, key it by `Repo.id` under
`cache/<feature_name>/` the same way, rather than reaching for the
"`<repo_root>/.ukorehub/`" pattern UkoreBrowser's own `BrowserConfig`
still uses (that one is a Maya-side tool bundled *inside* the repo itself,
a different situation — it isn't UkoreHub reaching into a repo it doesn't
own).
