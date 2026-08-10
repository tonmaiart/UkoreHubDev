<#
.SYNOPSIS
    Fast add + commit + push of this repo's app/ work to origin/main, then
    publishes app/'s contents (flattened) to the UkoreHubRelease repo.

.DESCRIPTION
    Two steps, run back to back:
    1. This repo (UkoreHubDev, remote `origin`): stages everything
       (`git add -A`) across the whole repo (app/, developer/, root files -
       everything currently sitting in the working tree), commits, and
       pushes to `origin/main` in one shot, with no per-file review or
       confirmation prompt - "fast" means exactly that. Never force-pushes
       `origin` - a rejected push (you're behind) or a failing pre-commit
       hook stops the script here and reports the git error; step 2 does
       not run in that case.
    2. Release repo (UkoreHubRelease, remote `release`, GitHub repo name
       `UkoreHub`): mirrors this repo's now-pushed `main` onto
       `release/main`, but only the `app/` subtree - `developer/`,
       `.claude/`, root `CLAUDE.md`/`README.md`/`pytest.ini`/
       `requirements-dev.txt`/`UkoreHubLauncher.exe` are never checked out
       in the first place, so there's no exclude-list to maintain; instead
       `app/`'s contents get flattened up to the release repo's root so it
       looks exactly like an UkoreHubDev checkout used to before the
       app/launcher merge. Runs even if step 1 had nothing new to commit,
       so re-running this after a release-only hiccup still catches the
       release repo up. Pass -NoRelease to skip this step.

.PARAMETER Message
    Commit message for step 1. Defaults to a timestamped "Fast commit"
    message if omitted.

.PARAMETER NoRelease
    Skip step 2 (publishing to the release repo) - push to origin/main only.

.EXAMPLE
    developer/release_app.ps1
    developer/release_app.ps1 -Message "WIP: cloud data admin plugin"
    developer/release_app.ps1 -NoRelease
#>
param(
    [string]$Message,
    [switch]$NoRelease
)

$ErrorActionPreference = "Stop"

$SourceBranch = "main"
$ReleaseRemoteName = "release"
$ReleaseRemoteUrl = "https://github.com/tonmaiart/UkoreHub.git"
$ReleaseBranch = "main"
$SyncBranch = "release-app-sync"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Not inside a git repository." }

$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $SourceBranch) {
    throw "release_app.ps1 must be run from this repo's '$SourceBranch' branch (currently on '$currentBranch')."
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
Write-Host "Publishing app/ to the release repo ($ReleaseRemoteName/$ReleaseBranch)..."

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

$worktreePath = Join-Path ([System.IO.Path]::GetTempPath()) "ukorehub-release-app-sync"
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

    # Pull in only the app/ subtree from this repo's main.
    git -C $worktreePath checkout $SourceBranch -- app
    if ($LASTEXITCODE -ne 0) { throw "git checkout $SourceBranch -- app failed." }

    # Flatten app/'s contents up to the worktree root, so the release
    # repo's root looks like a plain UkoreHubDev checkout always has -
    # developer/, .claude/, and every other root-level dev-only file were
    # never checked out above, so there's nothing left to explicitly
    # exclude. Uses -Force so hidden files (e.g. a stray .env-style config)
    # move too, then asserts app/ is actually empty before deleting it -
    # if anything got left behind, stop instead of silently dropping it.
    $appPath = Join-Path $worktreePath "app"
    Get-ChildItem -Path $appPath -Force | Move-Item -Destination $worktreePath -Force
    $leftover = Get-ChildItem -Path $appPath -Force | Measure-Object
    if ($leftover.Count -ne 0) {
        throw "Flatten left $($leftover.Count) item(s) behind in app/ - aborting before removing it. Inspect $appPath."
    }
    Remove-Item -Path $appPath -Recurse -Force

    git -C $worktreePath add -A
    git -C $worktreePath diff --cached --quiet
    $hasReleaseChanges = ($LASTEXITCODE -ne 0)

    if (-not $hasReleaseChanges) {
        Write-Host "$ReleaseRemoteName/$ReleaseBranch is already up to date with app/. Nothing to commit."
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
