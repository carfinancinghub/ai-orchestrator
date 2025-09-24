param(
  [string]$FrontPath = $env:FRONTEND_PATH,   # e.g. C:\Backup_Projects\CFH\frontend
  [string]$Stamp     = $env:stamp,           # optional; auto-detected if empty
  [switch]$DryRun                              # use -DryRun to preview writes
)

$ErrorActionPreference = "Stop"

function Get-FrontStamp {
  param([string]$Path)
  # 1) .orchestrator\stamp.txt
  $sf = Join-Path $Path ".orchestrator\stamp.txt"
  if (Test-Path $sf) {
    $s = (Get-Content $sf -Raw).Trim()
    if ($s) { return $s }
  }
  # 2) current branch like ts-migration/<stamp>
  try {
    $cur = git -C $Path branch --show-current 2>$null
    if ($cur -and $cur -match '^ts-migration/(.+)$') { return $Matches[1] }
  } catch {}
  # 3) latest remote ts-migration/*
  try {
    $heads = git -C $Path ls-remote --heads origin "ts-migration/*" 2>$null |
      ForEach-Object { ($_ -split "`t")[1] -replace '^refs/heads/','' } |
      Sort-Object
    if ($heads -and $heads.Count) {
      # last one is the newest by sort order (your stamps are sortable)
      $h = $heads[-1]
      if ($h -match '^ts-migration/(.+)$') { return $Matches[1] }
    }
  } catch {}
  # 4) fallback: now
  return (Get-Date -Format yyyyMMdd_HHmmss)
}

function Ensure-FrontPath([string]$Path) {
  if (-not $Path -or -not (Test-Path $Path)) {
    throw "Frontend path not found. Provide -FrontPath or set `\$env:FRONTEND_PATH`."
  }
}

# ---- Setup ----
Ensure-FrontPath $FrontPath
if (-not $Stamp -or -not $Stamp.Trim()) { $Stamp = Get-FrontStamp -Path $FrontPath }

# Export for node scripts
$env:FRONTEND_PATH = $FrontPath
$env:stamp         = $Stamp

Write-Host "Frontend: $FrontPath"
Write-Host "Stamp   : $Stamp"

# ---- Ensure analysis plan exists ----
$plan = Join-Path (Join-Path (Join-Path $PSScriptRoot "..") "reports\analysis") "$Stamp\plan.json" | Resolve-Path -ErrorAction SilentlyContinue
if (-not $plan) {
  Write-Host "No plan.json found for stamp; running analyzer…"
  node "$PSScriptRoot\..\app\analyze-frontend.mjs"
  $plan = Join-Path (Join-Path (Join-Path $PSScriptRoot "..") "reports\analysis") "$Stamp\plan.json"
}

if (-not (Test-Path $plan)) { throw "Plan not found: $plan" }

# ---- Synthesize stubs ----
$env:PLAN_PATH = $plan
$env:DRY_RUN   = ($DryRun.IsPresent ? "1" : "0")
node "$PSScriptRoot\..\app\synthesize-ts.mjs"

# ---- Commit & push (unless DryRun) ----
if (-not $DryRun) {
  Push-Location $FrontPath
  try {
    # show what's changed
    git status --porcelain
    # do not add node_modules even if present
    git add -A ":!node_modules"
    $staged = git diff --cached --name-only
    if (-not $staged) {
      Write-Host "No changes to commit."
    } else {
      # determine branch (should be ts-migration/<stamp>)
      $branch = git branch --show-current
      if (-not $branch) { $branch = "ts-migration/$Stamp" }
      git commit -m ("chore(ts-migration): add safe TSX stubs [{0}]" -f $Stamp)
      git push -u origin $branch
      Write-Host "Pushed changes to $branch"
    }
  } finally {
    Pop-Location
  }
} else {
  Write-Host "Dry run: no git changes performed."
}
