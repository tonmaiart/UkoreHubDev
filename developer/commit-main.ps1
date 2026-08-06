<#
.SYNOPSIS
    Mirrors this repo's main branch onto the UkoreHubRelease repo's main
    branch, stripping dev-only tooling, and pushes.

.DESCRIPTION
    This repo (UkoreHubDev, remote `origin`) is a dev repo through and
    through - its `main` branch IS the working branch (there's no separate
    `dev` branch here anymore). This script publishes the current state of
    that `main` to `main` on the separate UkoreHubRelease repo (remote
    `release`), excluding folders that should never ship to artists:
    `.claude/` and `developer/` (packaging, bug-history, GLOSSARY.md). Run
    from `main` with a clean working tree. Commits the result to a
    throwaway local branch (`release-sync`) built on top of the release
    remote's current main, and pushes that to release/main, unless -NoPush
    is passed. Auto-adds the `release` remote (pointing at
    $ReleaseRemoteUrl) if it isn't already configured.

.PARAMETER Message
    Commit message for the sync commit. Defaults to a message that
    references the commit being synced.

.PARAMETER NoPush
    Commit to the local `release-sync` branch but skip pushing to the
    release remote - review it yourself (git log release-sync / git show
    release-sync) and push manually when ready.

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
$SourceBranch = "main"
$ReleaseRemoteName = "release"
$ReleaseRemoteUrl = "https://github.com/tonmaiart/UkoreHub.git"
$ReleaseBranch = "main"
$SyncBranch = "release-sync"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Not inside a git repository." }

$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $SourceBranch) {
    throw "commit-main.ps1 must be run from this repo's '$SourceBranch' branch (currently on '$currentBranch')."
}

$statusOutput = git status --porcelain
if ($statusOutput) {
    throw "$SourceBranch has uncommitted or untracked changes - commit or stash them first:`n$statusOutput"
}

$sourceHead = git rev-parse --short HEAD
$sourceSubject = git log -1 --pretty=%s
if (-not $Message) {
    $Message = "Sync from ${SourceBranch} @ ${sourceHead}: $sourceSubject"
}

$configuredRemotes = git remote
if ($configuredRemotes -notcontains $ReleaseRemoteName) {
    Write-Host "Adding '$ReleaseRemoteName' remote ($ReleaseRemoteUrl)..."
    git remote add $ReleaseRemoteName $ReleaseRemoteUrl | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git remote add $ReleaseRemoteName failed." }
}
else {
    $existingReleaseUrl = git remote get-url $ReleaseRemoteName
    if ($existingReleaseUrl -ne $ReleaseRemoteUrl) {
        throw "Remote '$ReleaseRemoteName' already points to '$existingReleaseUrl', expected '$ReleaseRemoteUrl'."
    }
}

Write-Host "Fetching $ReleaseRemoteName..."
git fetch $ReleaseRemoteName | Out-Null
if ($LASTEXITCODE -ne 0) { throw "git fetch $ReleaseRemoteName failed." }

$hasRemoteMain = [bool](& { $ErrorActionPreference = "SilentlyContinue"; git rev-parse --verify --quiet "refs/remotes/$ReleaseRemoteName/$ReleaseBranch" 2>$null })

$worktreePath = Join-Path ([System.IO.Path]::GetTempPath()) "ukorehub-release-sync"
if (Test-Path $worktreePath) {
    & { $ErrorActionPreference = "SilentlyContinue"; git worktree remove --force $worktreePath 2>$null }
    if (Test-Path $worktreePath) { Remove-Item -Recurse -Force $worktreePath }
}
& { $ErrorActionPreference = "SilentlyContinue"; git branch -D $SyncBranch 2>$null } | Out-Null

if ($hasRemoteMain) {
    Write-Host "Checking out $ReleaseRemoteName/$ReleaseBranch into a temporary worktree..."
    git worktree add -B $SyncBranch $worktreePath "$ReleaseRemoteName/$ReleaseBranch" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed." }
}
else {
    Write-Host "$ReleaseRemoteName has no '$ReleaseBranch' yet - starting it fresh from this sync..."
    git worktree add --detach $worktreePath $sourceHead | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git worktree add failed." }
    git -C $worktreePath checkout --orphan $SyncBranch | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "git checkout --orphan $SyncBranch failed." }
}

try {
    # Clear the sync worktree's currently tracked files (index + working
    # tree), keep .git.
    git -C $worktreePath rm -r -q --cached . | Out-Null
    Get-ChildItem $worktreePath -Force |
        Where-Object { $_.Name -ne ".git" } |
        Remove-Item -Recurse -Force

    # Repopulate everything from this repo's main.
    git -C $worktreePath checkout $SourceBranch -- .
    if ($LASTEXITCODE -ne 0) { throw "git checkout $SourceBranch -- . failed." }

    # Strip dev-only tooling.
    foreach ($p in $excludePaths) {
        $full = Join-Path $worktreePath $p
        if (Test-Path $full) { Remove-Item -Recurse -Force $full }
    }

    git -C $worktreePath add -A
    git -C $worktreePath diff --cached --quiet
    $hasChanges = ($LASTEXITCODE -ne 0)

    if (-not $hasChanges) {
        Write-Host "$ReleaseRemoteName/$ReleaseBranch is already up to date with $SourceBranch (minus excluded paths). Nothing to commit."
    }
    else {
        git -C $worktreePath commit -m $Message | Out-Null
        $syncHead = git -C $worktreePath rev-parse --short HEAD
        Write-Host "Committed to ${SyncBranch}: $syncHead"
    }

    if ($NoPush) {
        Write-Host "Skipping push (-NoPush). Review with 'git log $SyncBranch' / 'git show $SyncBranch', then push yourself:"
        Write-Host "  git push $ReleaseRemoteName ${SyncBranch}:$ReleaseBranch"
    }
    else {
        Write-Host "Pushing $SyncBranch to $ReleaseRemoteName/$ReleaseBranch..."
        git -C $worktreePath push $ReleaseRemoteName "${SyncBranch}:$ReleaseBranch"
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Push failed - the sync commit exists locally on '$SyncBranch' but was NOT published. Resolve (e.g. 'git fetch $ReleaseRemoteName' and rebase, or check your connection) and push manually: git push $ReleaseRemoteName ${SyncBranch}:$ReleaseBranch"
        }
        else {
            Write-Host "Pushed to $ReleaseRemoteName/$ReleaseBranch."
            $pushedOk = $true
        }
    }
}
finally {
    & { $ErrorActionPreference = "SilentlyContinue"; git worktree remove --force $worktreePath 2>$null }
    if ($pushedOk) {
        & { $ErrorActionPreference = "SilentlyContinue"; git branch -D $SyncBranch 2>$null } | Out-Null
    }
}
