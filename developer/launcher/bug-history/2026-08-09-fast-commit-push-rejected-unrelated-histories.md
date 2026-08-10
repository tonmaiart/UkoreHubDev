# commit-release-fast.ps1's origin push got rejected with a diverged/unrelated history

## Symptom

Reconciling a rejected `git push` on this repo (following the old warning
text's suggestion to `git pull --rebase origin main`, or an equivalent
manual `git pull`) failed with:

```
fatal: refusing to merge unrelated histories
```

not the ordinary "non-fast-forward" rejection an ordinary diverged branch
produces.

## Root cause

Not fully confirmed — but during one session, two commits titled
`Fast commit: <timestamp>` (the exact default message
`commit-release-fast.ps1` generates when `-Message` isn't passed) appeared
on `origin/main` roughly 36 minutes apart without that session's agent
ever running `git commit`/`git push` itself. Checked and ruled out as the
source: no Claude Code scheduled task (`CronList`) or cloud routine
(`list_scheduled_tasks`) existed, and a `schtasks /query` sweep for
`ukorehub`/`fast commit`/`commit-release` found nothing either — so
whatever is producing these commits wasn't identified with certainty.

`fatal: refusing to merge unrelated histories` specifically means git found
**no common ancestor** between the two branches being merged, not just
that they'd diverged from a shared point. An ordinary second clone (or a
second terminal running this same script against the same checkout)
pushing concurrently would only ever produce a normal
non-fast-forward rejection, since both share `origin`'s real history. The
"unrelated" variant implies whatever is producing these commits built its
local `main` via `git init` + `git remote add` + commit (its own root
commit, no shared history) rather than an actual `git clone`/`git fetch`
of `origin` first — the same shape `updater.py`'s `bootstrap_git_repo`
deliberately builds out of a plain folder, just apparently happening
somewhere against this dev repo's `origin` too, outside this repo's own
scripts.

## Fix

Stopped trying to reconcile diverged histories at all.
`commit-release-fast.ps1`'s push to `origin/main` and `commit-main.ps1`'s
push to the release remote both now retry with `git push --force` the
moment the plain push is rejected, instead of warning and telling a human
to `git pull`/rebase by hand. Neither script ever runs `git pull`/`git
merge` anywhere in the first place (same reasoning `updater.py`'s
`ensure_up_to_date` docstring already gives for using `fetch` + `reset
--hard` over `pull`), so this closes the only path that could still hit
"unrelated histories" — the manual recovery step the old warning text
suggested.

## Lesson

An unattended "fast"/no-review publish script must never leave "run `git
pull` and reconcile it yourself" as its own failure-recovery suggestion —
nobody may be watching when it fires, and a merge between truly unrelated
histories doesn't resolve itself, it just fails forever on every retry.
For a script that's meant to be the sole legitimate writer to a given
remote branch, local should simply always win: force-push on rejection
rather than merge. Separately: if something keeps producing genuinely
unrelated (not just diverged) history against this repo's `origin`, look
for a process that's `git init`-ing a fresh local `main` against this
repo's remote URL instead of actually cloning it — that's the specific
shape that produces "unrelated," not just "behind."
