<#
.SYNOPSIS
    Fast add + commit + push of this repo's portal/ work to origin/main,
    then publishes portal/'s contents (flattened) to the UkoreHubPortal
    repo.

.DESCRIPTION
    Two steps, run back to back, mirroring release_app.ps1's own shape:
    1. This repo (UkoreHubDev, remote `origin`): stages everything
       (`git add -A`) across the whole repo (app/, portal/, developer/,
       root files - everything currently sitting in the working tree),
       commits, and pushes to `origin/main` in one shot, with no per-file
       review or confirmation prompt - "fast" means exactly that. Never
       force-pushes `origin` - a rejected push (you're behind) or a
       failing pre-commit hook stops the script here and reports the git
       error; step 2 does not run in that case.
    2. Release repo (UkoreHubPortal, remote `release-portal`, GitHub repo
       name `UkoreHubPortal`): mirrors this repo's now-pushed `main` onto
       `release-portal/main`, but only the `portal/` subtree - `app/`,
       `developer/`, `.claude/`, root `CLAUDE.md`/`README.md`/etc. are
       never checked out in the first place, so there's no exclude-list to
       maintain; instead `portal/`'s contents get flattened up to the
       release repo's root, same as `app/`'s own release. Runs even if
       step 1 had nothing new to commit, so re-running this after a
       release-only hiccup still catches the release repo up. Pass
       -NoRelease to skip this step.

    UkoreHubLauncher.exe bootstraps/updates the nested `portal/` clone on
    an artist machine from this same release repo (see
    developer/launcher/launcher_build/updater.py's PORTAL_REMOTE_URL) -
    run this (or `git release-portal`, once the alias is configured - see
    developer/README.md) any time portal/'s own code changes, the same way
    release_app.ps1 covers app/.

.PARAMETER Message
    Commit message for step 1. Defaults to a timestamped "Fast commit"
    message if omitted.

.PARAMETER NoRelease
    Skip step 2 (publishing to the release repo) - push to origin/main only.

.EXAMPLE
    developer/release_portal.ps1
    developer/release_portal.ps1 -Message "WIP: project dashboard"
    developer/release_portal.ps1 -NoRelease
#>
param(
    [string]$Message,
    [switch]$NoRelease
)

$ErrorActionPreference = "Stop"

$SourceBranch = "main"
$ReleaseRemoteName = "release-portal"
$ReleaseRemoteUrl = "https://github.com/tonmaiart/UkoreHubPortal.git"
$ReleaseBranch = "main"
$SyncBranch = "release-portal-sync"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Not inside a git repository." }

$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $SourceBranch) {
    throw "release_portal.ps1 must be run from this repo's '$SourceBranch' branch (currently on '$currentBranch')."
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
    Write-Warning "Skipping release-repo publish since the origin/$SourceBranch push above failed - fix that first, then run this script again."
    exit 1
}

Write-Host ""
Write-Host "Publishing portal/ to the release repo ($ReleaseRemoteName/$ReleaseBranch)..."

$sourceHead = git rev-parse --short HEAD
$sourceSubject = git log -1 --pretty=%s
$releaseMessage = "Sync from ${SourceBranch} @ ${sourceHead}: $sourceSubject"

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

$worktreePath = Join-Path ([System.IO.Path]::GetTempPath()) "ukorehub-release-portal-sync"
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

    # Pull in only the portal/ subtree from this repo's main.
    git -C $worktreePath checkout $SourceBranch -- portal
    if ($LASTEXITCODE -ne 0) { throw "git checkout $SourceBranch -- portal failed." }

    # Flatten portal/'s contents up to the worktree root, so the release
    # repo's root looks like a plain portal/ checkout - app/, developer/,
    # .claude/, and every other root-level dev-only file were never
    # checked out above, so there's nothing left to explicitly exclude.
    # Uses -Force so hidden files (e.g. portal/.gitignore) move too, then
    # asserts portal/ is actually empty before deleting it - if anything
    # got left behind, stop instead of silently dropping it.
    $portalPath = Join-Path $worktreePath "portal"
    Get-ChildItem -Path $portalPath -Force | Move-Item -Destination $worktreePath -Force
    $leftover = Get-ChildItem -Path $portalPath -Force | Measure-Object
    if ($leftover.Count -ne 0) {
        throw "Flatten left $($leftover.Count) item(s) behind in portal/ - aborting before removing it. Inspect $portalPath."
    }
    Remove-Item -Path $portalPath -Recurse -Force

    git -C $worktreePath add -A
    git -C $worktreePath diff --cached --quiet
    $hasReleaseChanges = ($LASTEXITCODE -ne 0)

    if (-not $hasReleaseChanges) {
        Write-Host "$ReleaseRemoteName/$ReleaseBranch is already up to date with portal/. Nothing to commit."
    }
    else {
        git -C $worktreePath commit -m $releaseMessage | Out-Null
        $syncHead = git -C $worktreePath rev-parse --short HEAD
        Write-Host "Committed to ${SyncBranch}: $syncHead"
    }

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
finally {
    & { $ErrorActionPreference = "SilentlyContinue"; git worktree remove --force $worktreePath 2>$null }
    if ($pushedOk) {
        & { $ErrorActionPreference = "SilentlyContinue"; git branch -D $SyncBranch 2>$null } | Out-Null
    }
}
