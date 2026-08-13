<#
.SYNOPSIS
    Rebuilds UkoreHubLauncher.exe, fast add + commit + push to origin/main,
    then publishes just the exe to the UkoreHubLauncher release repo.

.DESCRIPTION
    Three steps, run back to back:
    0. Rebuilds UkoreHubLauncher.exe
       (developer/launcher/launcher_build/build_exe.py) so whatever gets
       committed in step 1 is never stale relative to
       exe_entry.py/updater.py. A failed build stops the script here -
       nothing gets staged or committed.
    1. This repo (UkoreHubDev, remote `origin`): stages everything
       (`git add -A`) across the whole repo, commits, and pushes to
       `origin/main` in one shot, with no per-file review or confirmation
       prompt - "fast" means exactly that. Never uses --no-verify - a
       failing pre-commit hook still stops the script here. A rejected
       push (origin/main moved from something other than this checkout) is
       different: this script never stops to let a human reconcile that by
       hand - it force-pushes local main over whatever's on origin instead.
       Local is always authoritative here (see the ukorehub-launcher skill).
    2. Release repo (UkoreHubLauncher, remote `release-launcher`, added
       automatically if missing): mirrors just the tracked
       `UkoreHubLauncher.exe` file at this repo's root onto
       `release-launcher/main` - artists only need the exe itself, nothing
       else this repo carries is ever checked out for this publish. Runs
       even if step 1 had nothing new to commit, so re-running this after
       a release-only hiccup still catches the release repo up. Pass
       -NoRelease to skip this step.

.PARAMETER Message
    Commit message for step 1. Defaults to a timestamped "Fast commit"
    message if omitted.

.PARAMETER NoRelease
    Skip step 2 (publishing to the release repo) - push to origin/main only.

.EXAMPLE
    developer/release_launcher.ps1
    developer/release_launcher.ps1 -Message "Rebuild: v1.2.0 icon refresh"
    developer/release_launcher.ps1 -NoRelease
#>
param(
    [string]$Message,
    [switch]$NoRelease
)

$ErrorActionPreference = "Stop"

$SourceBranch = "main"
$ReleaseRemoteName = "release-launcher"
$ReleaseRemoteUrl = "https://github.com/tonmaiart/UkoreHubLauncher.git"
$ReleaseBranch = "main"
$SyncBranch = "release-launcher-sync"

$repoRoot = git rev-parse --show-toplevel
if (-not $repoRoot) { throw "Not inside a git repository." }

$currentBranch = git rev-parse --abbrev-ref HEAD
if ($currentBranch -ne $SourceBranch) {
    throw "release_launcher.ps1 must be run from this repo's '$SourceBranch' branch (currently on '$currentBranch')."
}

Write-Host "Rebuilding UkoreHubLauncher.exe (developer/launcher/launcher_build/build_exe.py)..."
python (Join-Path $repoRoot "developer/launcher/launcher_build/build_exe.py")
if ($LASTEXITCODE -ne 0) { throw "build_exe.py failed - exe was not rebuilt, nothing was committed." }

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
        Write-Warning "Push rejected (origin/$SourceBranch diverged) - force-pushing local $SourceBranch over it instead of reconciling."
        git push --force origin $SourceBranch
        if ($LASTEXITCODE -ne 0) {
            $originPushOk = $false
            Write-Warning "Force-push also failed - the commit exists locally ($newHead) but was NOT published. Check your connection/credentials, then push manually: git push --force origin $SourceBranch"
        }
        else {
            Write-Host "Force-pushed to origin/$SourceBranch."
        }
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
Write-Host "Publishing UkoreHubLauncher.exe to the release repo ($ReleaseRemoteName/$ReleaseBranch)..."

$sourceHead = git rev-parse --short HEAD
$sourceSubject = git log -1 --pretty=%s
$releaseMessage = "Sync from ${SourceBranch} @ ${sourceHead}: $sourceSubject"

# Never assumes the remote exists - first run on a machine that hasn't
# configured it yet just adds it, same pattern as release_app.ps1's
# `release` remote and the old commit-main.ps1 scripts.
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

$worktreePath = Join-Path ([System.IO.Path]::GetTempPath()) "ukorehublauncher-release-sync"
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

    # The release repo's root only ever holds this one tracked file - no
    # flatten step needed, unlike release_app.ps1's app/ subtree.
    git -C $worktreePath checkout $SourceBranch -- UkoreHubLauncher.exe
    if ($LASTEXITCODE -ne 0) { throw "git checkout $SourceBranch -- UkoreHubLauncher.exe failed." }

    git -C $worktreePath add -A
    git -C $worktreePath diff --cached --quiet
    $hasReleaseChanges = ($LASTEXITCODE -ne 0)

    if (-not $hasReleaseChanges) {
        Write-Host "$ReleaseRemoteName/$ReleaseBranch is already up to date. Nothing to commit."
    }
    else {
        git -C $worktreePath commit -m $releaseMessage | Out-Null
        $syncHead = git -C $worktreePath rev-parse --short HEAD
        Write-Host "Committed to ${SyncBranch}: $syncHead"
    }

    Write-Host "Pushing $SyncBranch to $ReleaseRemoteName/$ReleaseBranch..."
    git -C $worktreePath push $ReleaseRemoteName "${SyncBranch}:$ReleaseBranch"
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Push rejected ($ReleaseRemoteName/$ReleaseBranch diverged) - force-pushing $SyncBranch over it instead of reconciling."
        git -C $worktreePath push --force $ReleaseRemoteName "${SyncBranch}:$ReleaseBranch"
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Force-push also failed - the sync commit exists locally on '$SyncBranch' but was NOT published. Check your connection/credentials, then push manually: git push --force $ReleaseRemoteName ${SyncBranch}:$ReleaseBranch"
        }
        else {
            Write-Host "Force-pushed to $ReleaseRemoteName/$ReleaseBranch."
            $pushedOk = $true
        }
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
