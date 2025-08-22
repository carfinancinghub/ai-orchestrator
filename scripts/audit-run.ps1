<#
  File: scripts/audit-run.ps1
  Purpose: One-button runner for the JS/TS audit → plan → convert → (optional) commit (+ quarantine control).
  Requires: server app.server:app in this repo; Powershell 5+; Python venv active.
  Usage examples:
    ./scripts/audit-run.ps1 -Root "C:\Backup_Projects\CFH"
    ./scripts/audit-run.ps1 -Root "C:\Backup_Projects\CFH" -Convert -Commit
    ./scripts/audit-run.ps1 -Root "C:\Backup_Projects\CFH" -MinSizeBytes 200 -ExcludeRx '(?:/dist/|/build/|\.min\.(?:js|jsx)$)' -SameDirOnly -Convert
#>

param(
  [string]$JsList    = "C:\CFH\TruthSource\docs\file_scan_results_js_v1.md",
  [string]$JsxList   = "C:\CFH\TruthSource\docs\file_scan_results_jsx_v1.md",
  [string]$TsList    = "C:\CFH\TruthSource\docs\file_scan_results_ts_v1.md",
  [string]$TsxList   = "C:\CFH\TruthSource\docs\file_scan_results_tsx_v1.md",
  [string]$Root      = "C:\Backup_Projects\CFH",
  [int]$Port         = 8010,
  [int]$MinSizeBytes = 0,
  [string]$ExcludeRx = "",
  [switch]$SameDirOnly,
  [switch]$Convert,
  [switch]$Commit,
  [switch]$Quarantine = $true   # NEW: pass through to API (default on)
)

$ErrorActionPreference = 'Stop'
function Stamp { param([string]$msg) Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $msg) }

# Resolve and echo the port loudly (avoid weird console encoding issues)
$PortNum = if ($Port) { [int]$Port } else { 8010 }
Stamp ("Using Port: {0}" -f $PortNum)

# 0) stop any uvicorn listeners for this app & free the port
Stamp ("Stopping any uvicorn matching 'app.server:app' and anything listening on :{0} ..." -f $PortNum)
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'uvicorn .*app.server:app' } | ForEach-Object {
  try { Stop-Process -Id $_.ProcessId -Force } catch {}
}
Get-NetTCPConnection -LocalPort $PortNum -State Listen -EA SilentlyContinue | ForEach-Object {
  try { Stop-Process -Id $_.OwningProcess -Force } catch {}
}

# 1) (re)start server in background with env
Stamp ("Starting server on :{0} ..." -f $PortNum)
$env:AIO_PROVIDER='echo'
$env:AIO_DRY_RUN='false'
$py = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe'
$proc = Start-Process -PassThru $py -ArgumentList @('-m','uvicorn','app.server:app','--port',"$PortNum",'--log-level','warning')

# 2) wait until alive
Stamp ("Waiting for http://127.0.0.1:{0}/_debug/routes ..." -f $PortNum)
$ok = $false
foreach ($i in 1..60) {
  try {
    Invoke-RestMethod "http://127.0.0.1:$PortNum/_debug/routes" -TimeoutSec 1 | Out-Null
    $ok = $true; break
  } catch { Start-Sleep -Milliseconds 250 }
}
if (-not $ok) { throw ("Server did not start on :{0}" -f $PortNum) }
Stamp "Server is up."

# 3) build the plan
$exclude = if ([string]::IsNullOrEmpty($ExcludeRx)) { $null } else { [string]$ExcludeRx }
$body = @{
  md_paths       = @($JsList, $JsxList, $TsList, $TsxList)
  workspace_root = $Root
  size_min_bytes = [int]$MinSizeBytes
  exclude_regex  = $exclude
  same_dir_only  = [bool]$SameDirOnly
} | ConvertTo-Json -Depth 6

Stamp "POST /audit/js/plan ..."
$plan = Invoke-RestMethod -Method POST "http://127.0.0.1:$PortNum/audit/js/plan" -ContentType 'application/json' -Body $body

# Be robust if convert_in_root key doesn’t exist
$inRoot = if ($plan.counts.PSObject.Properties.Name -contains 'convert_in_root') { $plan.counts.convert_in_root } else { 0 }
Stamp ("PLAN OK: dedup={0} keep_ts_tsx={1} drop_js={2} convert_candidates={3} in_root={4}" -f `
  $plan.counts.dedup, $plan.counts.keep_ts_tsx, $plan.counts.drop_js_already_converted, $plan.counts.convert_candidates, $inRoot)
Stamp ("PLAN artifacts: json={0} csv={1}" -f $plan.plan_path, $plan.csv_path)

# 4) optionally convert
if ($Convert) {
  Stamp "POST /audit/js/convert (write=true, force=true) ..."
  $convBody = @{
    plan_path         = $plan.plan_path
    write             = $true
    force             = $true
    quarantine_failed = [bool]$Quarantine
  } | ConvertTo-Json
  $conv = Invoke-RestMethod -Method POST "http://127.0.0.1:$PortNum/audit/js/convert" -ContentType 'application/json' -Body $convBody
  Stamp ("CONVERT OK: tried={0} wrote={1} root={2}" -f $conv.tried, $conv.wrote, $conv.root)
}

# 5) optionally commit any existing TS files that correspond to converted JS
if ($Commit) {
  Stamp "POST /audit/js/commit (batch_size=200) ..."
  $c = Invoke-RestMethod -Method POST "http://127.0.0.1:$PortNum/audit/js/commit" -ContentType 'application/json' `
    -Body (@{ plan_path=$plan.plan_path; batch_size=200 } | ConvertTo-Json)
  Stamp ("COMMIT OK: ts_existing={0} commits={1} dry_run={2}" -f $c.ts_existing, $c.commits, $c.dry_run)
}

Stamp "Done."
