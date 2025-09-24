param(
  [string]$AIO      = "C:\c\ai-orchestrator",
  [string]$Frontend = "C:\Backup_Projects\CFH\frontend",
  [string]$Repo     = "carfinancinghub/cfh",
  [int]$Take        = 25
)

$ErrorActionPreference = "Stop"
Set-Location $AIO

# 1) load candidate list (already sorted by worth_score highest first)
$candFile = Join-Path "reports" "conversion_candidates.txt"
if (-not (Test-Path $candFile)) {
  throw "Missing $candFile. Run tools\cod1\make_inventory.ps1 -WriteCandidateList first."
}
$all = Get-Content $candFile | Where-Object { $_ -and -not $_.StartsWith("#") }

# 2) skip ones already converted (present in artifacts\generated as .ts or .tsx)
function Is-Converted([string]$srcPath) {
  $name = [IO.Path]::GetFileName($srcPath)
  $stem = [IO.Path]::GetFileNameWithoutExtension($name)
  $ts   = Join-Path "artifacts\generated" ($stem + ".ts")
  $tsx  = Join-Path "artifacts\generated" ($stem + ".tsx")
  (Test-Path $ts) -or (Test-Path $tsx)
}

$todo = @()
foreach ($p in $all) {
  if ($todo.Count -ge $Take) { break }
  if (-not (Is-Converted $p)) { $todo += $p }
}
if ($todo.Count -eq 0) {
  Write-Host "No remaining candidates to convert."
  exit 0
}

# 3) write a tiny python helper to a temp file (reads stdin, calls cod1)
$py = @'
import json, os, sys
from app.ops import cod1
files = [line.strip() for line in sys.stdin if line.strip()]
res = cod1(files, gh_repo=os.environ.get("AIO_GH_REPO",""))
print(json.dumps(res, indent=2))
'@
$tmp = Join-Path $env:TEMP ("cod1_run_candidates_{0}.py" -f (Get-Date -Format yyyyMMdd_HHmmss))
Set-Content -Path $tmp -Value $py -Encoding UTF8

# 4) run it: pipe the file list into python (stdin)
$env:AIO_GH_REPO = $Repo
$json = ($todo -join "`n") | & python $tmp

# 5) keep a debug copy
$debug = Join-Path "reports\debug" ("run_candidates_{0}.json" -f (Get-Date -Format yyyyMMdd_HHmmss))
New-Item -ItemType Directory -Force -Path (Split-Path $debug) | Out-Null
$json | Set-Content -Path $debug -Encoding UTF8

Write-Host "Processed $($todo.Count) candidates via cod1. Debug: $debug"
