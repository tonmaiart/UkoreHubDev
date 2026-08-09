<#
.SYNOPSIS
    Fast add + commit + push of this repo's current working tree straight to
    origin/main.

.DESCRIPTION
    For the day-to-day dev repo (UkoreHubDev, remote `origin`) only - this is
    NOT the UkoreHubRelease publish flow (see commit-main.ps1 for that, which
    targets a different remote/repo entirely and requires a clean tree
    first). This script stages everything (`git add -A`), commits, and
    pushes to `origin/main` in one shot, with no per-file review or
    confirmation prompt - "fast" means exactly that, so only use it when
    you're fine committing everything currently sitting in the working tree.
    Never uses --force or --no-verify; a push rejected by the remote (e.g.
    you're behind) or a failing pre-commit hook stops the script and reports
    the git error instead of working around it.

.PARAMETER Message
    Commit message. Defaults to a timestamped "Fast commit" message if
    omitted.

.EXAMPLE
    developer/commit-release-fast.ps1
    developer/commit-release-fast.ps1 -Message "WIP: cloud data admin plugin"
#>
param(
    [string]$Message
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
if (-not $hasChanges) {
    Write-Host "Nothing staged - working tree already matches HEAD. Nothing to commit."
    exit 0
}

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
    Write-Warning "Push failed - the commit exists locally ($newHead) but was NOT published. Resolve (e.g. 'git pull --rebase origin $SourceBranch') and push manually: git push origin $SourceBranch"
}
else {
    Write-Host "Pushed to origin/$SourceBranch."
}
