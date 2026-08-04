<#
.SYNOPSIS
    Mirrors the dev branch onto main, stripping dev-only tooling, and pushes.

.DESCRIPTION
    Publishes the current state of `dev` to `main`, excluding folders that
    should never ship to artists: `.claude/` and `developer/` (packaging,
    bug-history, GLOSSARY.md). Run from the dev branch with a clean working
    tree. Commits the result to local main and pushes it to origin/main,
    unless -NoPush is passed.

.PARAMETER Message
    Commit message for the sync commit on main. Defaults to a message that
    references the dev commit being synced.

.PARAMETER NoPush
    Commit to local main but skip pushing to origin - review it yourself
    (git log main / git show main) and push manually when ready.

.EXAMPLE
    developer/commit-main.ps1
    developer/commit-main.ps1 -Message "Release: plugin catalog rework"
    developer/commit-main.ps1 -NoPush
#>
param(
    [string]$Message,
    [switch]$NoPush
)

$ErrorActionPreference = "Stop"

$excludePaths = @(".claude", "developer")

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Not inside a git repository." }

$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne "dev") {
    throw "commit-main.ps1 must be run from the dev branch (currently on '$currentBranch')."
}

$statusOutput = git status --porcelain
if ($statusOutput) {
    throw "dev has uncommitted or untracked changes - commit or stash them first:`n$statusOutput"
}

$devHead = git rev-parse --short HEAD
$devSubject = git log -1 --pretty=%s
if (-not $Message) {
    $Message = "Sync from dev @ ${devHead}: $devSubject"
}

$worktreePath = Join-Path ([System.IO.Path]::GetTempPath()) "ukorehub-main-sync"
if (Test-Path $worktreePath) {
    git worktree remove --force $worktreePath 2>$null
    if (Test-Path $worktreePath) { Remove-Item -Recurse -Force $worktreePath }
}

Write-Host "Checking out main into a temporary worktree..."
git worktree add $worktreePath main | Out-Null
if ($LASTEXITCODE -ne 0) { throw "git worktree add failed." }

try {
    # Clear main's currently tracked files (index + working tree), keep .git.
    git -C $worktreePath rm -r -q --cached . | Out-Null
    Get-ChildItem $worktreePath -Force |
        Where-Object { $_.Name -ne ".git" } |
        Remove-Item -Recurse -Force

    # Repopulate everything from dev's tree.
    git -C $worktreePath checkout dev -- .
    if ($LASTEXITCODE -ne 0) { throw "git checkout dev -- . failed." }

    # Strip dev-only tooling.
    foreach ($p in $excludePaths) {
        $full = Join-Path $worktreePath $p
        if (Test-Path $full) { Remove-Item -Recurse -Force $full }
    }

    git -C $worktreePath add -A
    git -C $worktreePath diff --cached --quiet
    $hasChanges = ($LASTEXITCODE -ne 0)

    if (-not $hasChanges) {
        Write-Host "main is already up to date with dev (minus excluded paths). Nothing to commit."
    }
    else {
        git -C $worktreePath commit -m $Message | Out-Null
        $mainHead = git -C $worktreePath rev-parse --short HEAD
        Write-Host "Committed to main: $mainHead"
    }

    if ($NoPush) {
        Write-Host "Skipping push (-NoPush). Review with 'git log main' / 'git show main', then push yourself:"
        Write-Host "  git push origin main"
    }
    else {
        Write-Host "Pushing main to origin..."
        git -C $worktreePath push origin main
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Push failed - main was committed locally but NOT published. Resolve (e.g. 'git pull --rebase origin main' or check your connection) and push manually: git push origin main"
        }
        else {
            Write-Host "Pushed to origin/main."
        }
    }
}
finally {
    git worktree remove --force $worktreePath 2>$null
}
