<# 
  File: scripts/agent-run.ps1
  Purpose: Incremental JS->TS migration agent. Repeats plan -> convert small batch -> (optional) commit,
           stopping when remaining in-root candidates drop below a threshold.
  Requires: server app.server:app in this repo; PowerShell 5+; Python venv active.

  Examples:
    ./scripts/agent-run.ps1 -Root "C:\Backup_Projects\CFH" -MaxWrites 200 -Threshold 1200
    ./scripts/agent-run.ps1 -Root "C:\Backup_Projects\CFH" -MaxWrites 500 -Threshold 1500 -Commit
#>

param(
  [string]$JsList    = "C:\CFH\TruthSource\docs\file_scan_results_js_v1.md",
  [string]$JsxList   = "C:\CFH\TruthSource\docs\file_scan_results_jsx_v1.md",
  [string]$TsList    = "C:\CFH\TruthSource\docs\file_scan_results_ts_v1.md",
  [string]$TsxList   = "C:\CFH\TruthSource\docs\file_scan_results_tsx_v1.md",
  [string]$Root      = "C:\Backup_Projects\CFH",
  [int]$Port         = 8010,
  [int]$MaxWrites    = 200,
  [int]$Threshold    = 1200,
  [switch]$Commit
)

$ErrorActionPreference = 'Stop'
function Stamp { param([string]$m) Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) }

# Resolve python executable
$py = $null
if ($env:VIRTUAL_ENV) {
  $py = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
}
if (-not $py -or -not (Test-Path $py)) { $py = 'python' }

# Ensure server is up (same pattern as audit-run)
Stamp ("Ensuring server on :{0} ..." -f $Port)

# Kill any existing uvicorn app.server:app on this port
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn .*app.server:app' } | ForEach-Object {
  try { Stop-Process -Id $_.ProcessId -Force } catch {}
}
Get-NetTCPConnection -LocalPort $Port -State Listen -EA SilentlyContinue | ForEach-Object {
  try { Stop-Process -Id $_.OwningProcess -Force } catch {}
}

$env:AIO_PROVIDER='echo'
$env:AIO_DRY_RUN='false'

$proc = Start-Process -PassThru $py -ArgumentList @('-m','uvicorn','app.server:app','--port',"$Port",'--log-level','warning')
$ok = $false
for ($i=0; $i -lt 60; $i++) {
  if ($proc.HasExited) {
    Stamp ("Uvicorn exited with code {0}. Dumping last 200 log lines..." -f $proc.ExitCode)
    if (Test-Path $uvLog) { Get-Content $uvLog -Tail 200 }
    throw "Server failed to start"
  }
  try {
    Invoke-RestMethod "http://127.0.0.1:$Port/_debug/routes" -TimeoutSec 1 | Out-Null
    $ok=$true; break
  } catch {
    Start-Sleep -Milliseconds 500
  }
}

if (-not $ok) { throw ("Server did not come up on :{0}" -f $Port) }
Stamp "Server is up."

# Ensure 'requests' exists
$hasReq = $false
& $py -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('requests') else 1)"
if ($LASTEXITCODE -eq 0) { $hasReq = $true }

# Ensure 'uvicorn' exists
$hasUv = $false
& $py -c "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('uvicorn') else 1)"
if ($LASTEXITCODE -eq 0) { $hasUv = $true }
if (-not $hasUv) {
  Stamp "Installing python 'uvicorn' ..."
  & $py -m pip install -q uvicorn | Out-Null
}
if (-not $hasReq) {
  Stamp "Installing python 'requests' ..."
  & $py -m pip install -q requests | Out-Null
}

function Build-Plan {
  param([string]$Root)
  $body = @{
    md_paths       = @($JsList, $JsxList, $TsList, $TsxList)
    workspace_root = $Root
    size_min_bytes = 0
    exclude_regex  = $null
    same_dir_only  = $false
  } | ConvertTo-Json -Depth 6
  return Invoke-RestMethod -Method POST "http://127.0.0.1:$Port/audit/js/plan" -ContentType 'application/json' -Body $body
}

function Convert-Batch {
  param([string]$PlanPath, [string[]]$Batch)
  # Write a minimal mini-plan artifact
  $mini = @{
    workspace_root = $Root
    convert_candidates_in_root = $Batch
  } | ConvertTo-Json -Depth 5
  if (-not (Test-Path "artifacts")) { New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null }
  $miniPath = Join-Path "artifacts" ("agent_batch_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
  [System.IO.File]::WriteAllText($miniPath, $mini, [System.Text.UTF8Encoding]::new($false))

  $payload = @{ plan_path=$miniPath; write=$true; force=$true } | ConvertTo-Json
  return Invoke-RestMethod -Method POST "http://127.0.0.1:$Port/audit/js/convert" -ContentType 'application/json' -Body $payload
}

function Commit-TS {
  param([string]$PlanPath)
  $payload = @{ plan_path=$PlanPath; batch_size=200 } | ConvertTo-Json
  return Invoke-RestMethod -Method POST "http://127.0.0.1:$Port/audit/js/commit" -ContentType 'application/json' -Body $payload
}

# Main loop
$round = 0
while ($true) {
  $round += 1
  Stamp ("Round {0}: planning ..." -f $round)
  $plan = Build-Plan -Root $Root
  $counts = $plan.counts
  $inRoot = 0
  if ($counts -and ($counts.PSObject.Properties.Name -contains 'convert_in_root')) {
    $inRoot = [int]$counts.convert_in_root
  }
  Stamp ("Counts: in_root={0} total={1} keep={2} drop_js={3}" -f $inRoot, $counts.convert_candidates, $counts.keep_ts_tsx, $counts.drop_js_already_converted)

  if ($inRoot -le [int]$Threshold) {
    Stamp ("Below threshold ({0} <= {1}) - stopping." -f $inRoot, $Threshold)
    break
  }

  # Load full plan JSON to pick a batch
  $pj = Get-Content $plan.plan_path -Raw | ConvertFrom-Json
  $cands = @()
  if ($pj.PSObject.Properties.Name -contains 'convert_candidates_in_root') {
    $cands = $pj.convert_candidates_in_root
  } else {
    $cands = $pj.convert_candidates
  }

  # Pick up to MaxWrites that exist and are in root
  $picked = @()
$newly  = @()
foreach ($p in $cands) {
  if ($picked.Count -ge [int]$MaxWrites) { break }
  if (-not (Test-Path $p)) { continue }
  if (-not ($p -like ("{0}*" -f $Root))) { continue }  # safety: ensure under Root
  $tsSibling = [System.IO.Path]::ChangeExtension($p, "ts")
  if (Test-Path $tsSibling) { continue }               # skip if already converted
  if ($seen.Contains($p)) { continue }                 # skip if we already tried this path
  $picked += $p
  $newly  += $p
}
if ($newly.Count -gt 0) {
  $dir = Split-Path $seenFile -Parent
  if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
  Add-Content -Path $seenFile -Value ($newly -join [Environment]::NewLine)
  foreach ($x in $newly) { [void]$seen.Add($x) }
}

  if ($picked.Count -eq 0) {
    Stamp "No eligible files found in this round - stopping."
    break
  }

  Stamp ("Converting batch of {0} ..." -f $picked.Count)
  $conv = Convert-Batch -PlanPath $plan.plan_path -Batch $picked
  Stamp ("Converted: tried={0} wrote={1}" -f $conv.tried, $conv.wrote)

  if ($Commit) {
    Stamp "Committing changed TS files ..."
    $c = Commit-TS -PlanPath $plan.plan_path
    Stamp ("Commit result: ts_existing={0} commits={1} dry_run={2}" -f $c.ts_existing, $c.commits, $c.dry_run)
  }

  Start-Sleep -Seconds 2
}

Stamp "Agent finished."



