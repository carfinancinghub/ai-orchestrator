<#
  scripts/ci/report.ps1
  Self-contained helpers to:
   - Normalize paths (To-Posix)
   - Derive owner/repo from git remote (SSH/HTTPS)
   - Compute a GitHub blob URL for a given file path (absolute or repo-relative)
   - Optionally append a SUMMARY line into a log file

  Usage:
    pwsh -File scripts/ci/report.ps1 `
      -Path "reports\debug\some_log.md" `
      -Branch "fix/restore-report-docs" `
      -RepoRoot (Get-Location).Path `
      -AppendTo "reports\debug\summary.txt"
#>

param(
  [Parameter(Mandatory=$true)]
  [string] $Path,

  [Parameter(Mandatory=$false)]
  [string] $RepoRoot = (Get-Location).Path,

  [Parameter(Mandatory=$false)]
  [string] $Branch = $env:GIT_BRANCH,

  [Parameter(Mandatory=$false)]
  [string] $AppendTo
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function To-Posix([string]$p) {
  return ($p -replace "\\","/")
}

function Get-OwnerRepo([string]$repoPath) {
  $remote = git -C $repoPath remote get-url origin 2>$null
  if ($remote -match "github\.com[:/](.+?)(\.git)?$") { return $Matches[1] }
  return $null
}

# Validate repo
if (-not (Test-Path (Join-Path $RepoRoot ".git"))) {
  throw "Not a git repo: $RepoRoot"
}

# Branch fallback
if ([string]::IsNullOrWhiteSpace($Branch)) { $Branch = "fix/restore-report-docs" }

$ownerRepo = Get-OwnerRepo -repoPath $RepoRoot
if (-not $ownerRepo) { throw "Could not derive owner/repo from remote in $RepoRoot" }

# Resolve file & compute relative path
$repoPosix = To-Posix (Resolve-Path $RepoRoot)
$pathFull  = To-Posix (Resolve-Path $Path)
if ($pathFull.StartsWith("$repoPosix/")) {
  $rel = $pathFull.Substring($repoPosix.Length + 1)
} else {
  # Still produce a URL-ish string (may not be valid in GitHub)
  $rel = $pathFull
}

$blobUrl = "https://github.com/$ownerRepo/blob/$Branch/$rel"

# Print to console for CI logs
"GitHub blob: $blobUrl" | Write-Output

# Optional: append a SUMMARY line
if ($AppendTo) {
  $appendDir = Split-Path $AppendTo
  if ($appendDir -and -not (Test-Path $appendDir)) { New-Item -ItemType Directory -Force -Path $appendDir | Out-Null }
  "**GitHub log:** $blobUrl" | Out-File $AppendTo -Append -Encoding UTF8
}
