<#
.SYNOPSIS
    Fast add + commit + push of this repo's current working tree straight to
    origin/main, then publishes the result to the UkoreHubRelease repo too.

.DESCRIPTION
    Two steps, run back to back:
    1. Dev repo (UkoreHubDev, remote `origin`): stages everything
       (`git add -A`), commits, and pushes to `origin/main` in one shot, with
       no per-file review or confirmation prompt - "fast" means exactly
       that, so only use it when you're fine committing everything currently
       sitting in the working tree. Never uses --force or --no-verify; a
       push rejected by the remote (e.g. you're behind) or a failing
       pre-commit hook stops the script here and reports the git error
       instead of working around it - step 2 below does not run in that
       case.
    2. Release repo (UkoreHubRelease, remote `release`): calls
       commit-main.ps1 unchanged, which mirrors this repo's now-pushed
       `main` onto `release/main` (stripping `.claude/`/`developer/`). Runs
       even if step 1 had nothing new to commit, so re-running this after a
       release-only hiccup still catches the release repo up. Pass
       -NoRelease to skip this step and only do step 1, same as running the
       old origin-only version of this script.

.PARAMETER Message
    Commit message for step 1. Defaults to a timestamped "Fast commit"
    message if omitted. Step 2 always uses commit-main.ps1's own default
    message (which already references the commit being synced) - not
    overridable from here.

.PARAMETER NoRelease
    Skip step 2 (publishing to the release repo) - push to origin/main only.

.EXAMPLE
    developer/commit-release-fast.ps1
    developer/commit-release-fast.ps1 -Message "WIP: cloud data admin plugin"
    developer/commit-release-fast.ps1 -NoRelease
#>
param(
    [string]$Message,
    [switch]$NoRelease
)

$ErrorActionPreference = "Stop"

$SourceBranch = "main"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Not inside a git repository." }

$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $SourceBranch) {
    throw "commit-release-fast.ps1 must be run from this repo's '$SourceBranch' branch (currently on '$currentBranch')."
}

git add -A
if ($LASTEXITCODE -ne 0) { throw "git add -A failed." }

git diff --cached --quiet
$hasChanges = ($LASTEXITCODE -ne 0)

$originPushOk = $true

if (-not $hasChanges) {
    Write-Host "Nothing staged - working tree already matches HEAD. Nothing to commit."
}
else {
    if (-not $Message) {
        $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
        $Message = "Fast commit: $timestamp"
    }

    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { throw "git commit failed." }

    $newHead = git rev-parse --short HEAD
    Write-Host "Committed: $newHead"

    Write-Host "Pushing $SourceBranch to origin/$SourceBranch..."
    git push origin $SourceBranch
    if ($LASTEXITCODE -ne 0) {
        $originPushOk = $false
        Write-Warning "Push failed - the commit exists locally ($newHead) but was NOT published. Resolve (e.g. 'git pull --rebase origin $SourceBranch') and push manually: git push origin $SourceBranch"
    }
    else {
        Write-Host "Pushed to origin/$SourceBranch."
    }
}

if ($NoRelease) {
    exit 0
}

if (-not $originPushOk) {
    Write-Warning "Skipping release-repo publish since the origin/$SourceBranch push above failed - fix that first, then run this script again (or run developer/commit-main.ps1 directly once origin is up to date)."
    exit 1
}

Write-Host ""
Write-Host "Publishing to the release repo (commit-main.ps1)..."
$commitMainScript = Join-Path $PSScriptRoot "commit-main.ps1"
try {
    & $commitMainScript
}
catch {
    Write-Warning "origin/$SourceBranch is up to date, but publishing to the release repo failed: $_"
    Write-Warning "Resolve the issue, then run 'developer/commit-main.ps1' yourself when ready."
    exit 1
}
