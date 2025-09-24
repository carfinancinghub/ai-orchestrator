# tools\cod1\upload_run_artifacts.ps1
param(
  [string]$AIO        = "C:\c\ai-orchestrator",
  [string]$RunId      = "",                        # optional: autodetect newest
  [string]$RepoPrefix = "generated",               # repo path prefix for files
  [switch]$UseRolling,                             # set rolling PR env and reuse
  [string]$HeadBranch = "ts-migration/rolling",    # rolling branch name
  [switch]$AndComment,                             # run gates + PR comment after upload
  [string]$Frontend  = "C:\Backup_Projects\CFH\frontend"  # used only when -AndComment
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

function Get-GeneratedFilesForRun([string]$rid) {
  $sugDir = Join-Path "artifacts\suggestions" $rid
  if (-not (Test-Path $sugDir)) { return @() }

  $out = @()
  Get-ChildItem $sugDir -File -Filter *.json | ForEach-Object {
    # e.g. "foo.test.jsx.json" -> stem "foo.test.jsx"
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)

    if ($stem.EndsWith(".jsx")) {
      $base = $stem.Substring(0, $stem.Length - 4)
      $candidate = Join-Path "artifacts\generated" ($base + ".tsx")
      if (Test-Path $candidate) { $out += (Get-Item $candidate) }
    }
    elseif ($stem.EndsWith(".js")) {
      $base = $stem.Substring(0, $stem.Length - 3)
      $candidate = Join-Path "artifacts\generated" ($base + ".ts")
      if (Test-Path $candidate) { $out += (Get-Item $candidate) }
    }
    else {
      # Rare: suggestions stem already matches .ts/.tsx
      $ts  = Join-Path "artifacts\generated" ($stem + ".ts")
      $tsx = Join-Path "artifacts\generated" ($stem + ".tsx")
      if (Test-Path $ts)  { $out += (Get-Item $ts)  }
      if (Test-Path $tsx) { $out += (Get-Item $tsx) }
    }
  }
  return $out
}


if (-not $RunId -or $RunId.Trim() -eq "") { $RunId = Get-LatestRunId }
if (-not $RunId) { throw "No RunId found. Generate a batch first." }

# Pick generated files for this run (fallback to all if none found)
$files = Get-GeneratedFilesForRun $RunId
if (-not $files -or $files.Count -eq 0) {
  $latest = (Get-ChildItem "artifacts\suggestions" -Directory |
             Sort-Object Name -Descending | Select-Object -First 1).Name
  if ($latest) {
    Write-Host "No matches for $RunId, falling back to newest: $latest"
    $files = Get-GeneratedFilesForRun $latest
    $RunId = $latest
  }
}

if (-not $files -or $files.Count -eq 0) {
  Write-Warning "No per-run matches; falling back to ALL artifacts\generated/*"
  $files = Get-ChildItem "artifacts\generated" -File -Recurse
}
if (-not $files -or $files.Count -eq 0) { throw "No files to upload." }

# Configure rolling branch env if requested
if ($UseRolling) {
  $env:AIO_UPLOAD_TS     = "0"
  $env:AIO_UPLOAD_BRANCH = $HeadBranch
} else {
  $env:AIO_UPLOAD_TS     = "1"
  $env:AIO_UPLOAD_BRANCH = ""
}

# Prepare env for inline Python call
$env:FILES       = [string]::Join("`n", ($files | ForEach-Object { $_.FullName }))
$env:RUN_ID      = $RunId
$env:REPO_PREFIX = $RepoPrefix

$py = @'
from app.ops import upload_to_github
import os, pathlib
files = [pathlib.Path(p) for p in os.environ.get("FILES","").splitlines() if p.strip()]
repo_prefix = os.environ.get("REPO_PREFIX","generated").strip("/")

repo_files = [(f"{repo_prefix}/{p.name}", p) for p in files if p.exists()]
if not repo_files:
    raise SystemExit("No valid repo files (from FILES).")
url = upload_to_github(os.environ.get("RUN_ID","manual"), repo_files)
print(url)
'@

# Upload and show PR URL (capture only the URL line)
$raw = $py | python -
$prUrl = ($raw -split "`r?`n" |
  Where-Object { $_ -match '^https?://.+/pull/\d+$' } |
  Select-Object -Last 1)

if (-not $prUrl) { throw "Upload returned no PR URL. Full output:`n$raw" }
Write-Host "PR URL: $prUrl"


# Optionally run gates locally and comment to PR (reuses your existing script)
if ($AndComment) {
  & .\tools\cod1\gates_local_and_comment.ps1 -AIO $AIO -Frontend $Frontend
}

