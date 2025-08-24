param(
  [Parameter(Mandatory=$true)][string]$Root,
  [Parameter(Mandatory=$true)][string]$JsList,
  [Parameter(Mandatory=$true)][string]$JsxList,
  [Parameter(Mandatory=$true)][string]$TsList,
  [Parameter(Mandatory=$true)][string]$TsxList,
  [int]$Port = 8010,
  [int]$MaxWrites = 200,
  [int]$Threshold = 1200,
  [switch]$Commit
)

$ErrorActionPreference = 'Stop'
function Stamp { param([string]$m) Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) }

function Read-MdPaths {
  param([string]$File)
  $out = @()
  if (-not (Test-Path $File)) { return $out }
  foreach ($m in (Select-String -Path $File -Pattern '^\s*-\s*(.+)$' -ErrorAction SilentlyContinue)) {
    if ($m.Matches.Count -gt 0) { $out += $m.Matches[0].Groups[1].Value.Trim() }
  }
  return $out
}

function Compute-Candidates {
  param([string]$Root, [string[]]$JsPaths, [string[]]$JsxPaths)
  $all = @($JsPaths + $JsxPaths)
  $uniq = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
  $cand = New-Object System.Collections.Generic.List[string]
  foreach ($p in $all) {
    if (-not $p) { continue }
    if (-not (Test-Path $p)) { continue }
    if (-not ($p -like ("{0}*" -f $Root))) { continue }
    $lower = $p.ToLowerInvariant()
    if ($lower -match '\\tests?(\\|$)' -or
        $lower -match '\\__snapshots__(\\|$)' -or
        $lower -match 'manualy_editing_files\\recovered') { continue }
    $ts  = [System.IO.Path]::ChangeExtension($p, "ts")
    $tsx = [System.IO.Path]::ChangeExtension($p, "tsx")
    if ((Test-Path $ts) -or (Test-Path $tsx)) { continue }
    if ($uniq.Add($p)) { $cand.Add($p) | Out-Null }
  }
  return ,$cand
}

function Ensure-Server {
  param([int]$Port)
  $py = $null
  if ($env:VIRTUAL_ENV) { $py = Join-Path $env:VIRTUAL_ENV 'Scripts\python.exe' }
  if ((-not $py) -or (-not (Test-Path $py))) { $py = 'python' }

  Stamp ("Ensuring server on :{0} ..." -f $Port)
  Get-CimInstance Win32_Process | ? { $_.CommandLine -match 'uvicorn .*app.server:app' } | % { try { Stop-Process -Id $_.ProcessId -Force } catch {} }
  Get-NetTCPConnection -LocalPort $Port -State Listen -EA SilentlyContinue | % { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }

  $env:AIO_PROVIDER='echo'; $env:AIO_DRY_RUN='false'
  $proc = Start-Process -PassThru $py -ArgumentList @('-m','uvicorn','app.server:app','--port',"$Port",'--log-level','warning')

  $ok = $false
  for ($i=0; $i -lt 60; $i++) {
    if ($proc.HasExited) { throw ("Uvicorn exited with code {0}" -f $proc.ExitCode) }
    try { irm "http://127.0.0.1:$Port/_debug/routes" -TimeoutSec 1 | Out-Null; $ok=$true; break } catch { Start-Sleep -Milliseconds 300 }
  }
  if (-not $ok) { throw "Server did not come up" }
  Stamp "Server is up."
}

function Convert-Batch {
  param([string]$Root, [string[]]$Batch, [int]$Port, [hashtable]$Bundle)
  if (-not (Test-Path "artifacts")) { New-Item -ItemType Directory -Force -Path "artifacts" | Out-Null }
  $mini = @{
    workspace_root = $Root
    convert_candidates_in_root = $Batch
    bundle_by_src = $Bundle
  } | ConvertTo-Json -Depth 12
  $miniPath = Join-Path "artifacts" ("agent_batch_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
  [System.IO.File]::WriteAllText($miniPath, $mini, [System.Text.UTF8Encoding]::new($false))
  $payload = @{ plan_path=$miniPath; write=$true; force=$true } | ConvertTo-Json
  return irm -Method POST "http://127.0.0.1:$Port/audit/js/convert" -ContentType 'application/json' -Body $payload
}

function Commit-TS {
  param([string]$PlanPath, [int]$Port)
  $payload = @{ plan_path=$PlanPath; batch_size=200 } | ConvertTo-Json
  return irm -Method POST "http://127.0.0.1:$Port/audit/js/commit" -ContentType 'application/json' -Body $payload
}

# --- Run ---
Ensure-Server -Port $Port

$round = 0
$sanDir = Split-Path -Parent $JsList
$testsList = Join-Path $sanDir "file_scan_results_tests_sanitized.md"
$docsList  = Join-Path $sanDir "file_scan_results_docs_sanitized.md"

while ($true) {
  $round += 1
  Stamp ("Round {0}: planning (plan-free) ..." -f $round)

  $jsPaths  = Read-MdPaths -File $JsList
  $jsxPaths = Read-MdPaths -File $JsxList
  $cand     = Compute-Candidates -Root $Root -JsPaths $jsPaths -JsxPaths $jsxPaths

  $inRoot = $cand.Count
  Stamp ("Local preflight counts: in_root={0} js_md={1} jsx_md={2}" -f $inRoot, $jsPaths.Count, $jsxPaths.Count)

  if ($inRoot -le [int]$Threshold) {
    Stamp ("Below threshold ({0} <= {1}) - stopping." -f $inRoot, $Threshold)
    break
  }

  # build indices for tests/docs by basename
  $testsIdx = @{}
  if (Test-Path $testsList) {
    foreach ($t in (Select-String -Path $testsList -Pattern '^\s*-\s*(.+)$' -ErrorAction SilentlyContinue)) {
      $fp = $t.Matches[0].Groups[1].Value.Trim()
      $bn = [System.IO.Path]::GetFileNameWithoutExtension($fp) -replace '\.test$',''
      if (-not $testsIdx.ContainsKey($bn)) { $testsIdx[$bn] = New-Object System.Collections.Generic.List[string] }
      $testsIdx[$bn].Add($fp) | Out-Null
    }
  }
  $docsIdx = @{}
  if (Test-Path $docsList) {
    foreach ($d in (Select-String -Path $docsList -Pattern '^\s*-\s*(.+)$' -ErrorAction SilentlyContinue)) {
      $fp = $d.Matches[0].Groups[1].Value.Trim()
      $bn = [System.IO.Path]::GetFileNameWithoutExtension($fp)
      if (-not $docsIdx.ContainsKey($bn)) { $docsIdx[$bn] = New-Object System.Collections.Generic.List[string] }
      $docsIdx[$bn].Add($fp) | Out-Null
    }
  }

  $picked = @()
  foreach ($p in $cand) {
    if ($picked.Count -ge [int]$MaxWrites) { break }
    $picked += $p
  }

  if ($picked.Count -eq 0) {
    Stamp "No eligible files found in this round - stopping."
    break
  }

  # bundle_by_src only for the picked batch
  $bundle = @{}
  foreach ($p in $picked) {
    $bn = [System.IO.Path]::GetFileNameWithoutExtension($p)
    $bundle[$p] = @{
      tests = $(if ($testsIdx.ContainsKey($bn)) { @($testsIdx[$bn]) } else { @() })
      docs  = $(if ($docsIdx.ContainsKey($bn))  { @($docsIdx[$bn])  } else { @() })
    }
  }

  Stamp ("Converting batch of {0} ..." -f $picked.Count)
  $conv = Convert-Batch -Root $Root -Batch $picked -Port $Port -Bundle $bundle
  Stamp ("Converted: tried={0} wrote={1}" -f $conv.tried, $conv.wrote)

  if ($Commit) {
    $lastPlan = Get-ChildItem artifacts\agent_batch_*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($lastPlan) {
      Stamp "Committing changed TS files ..."
      $c = Commit-TS -PlanPath $lastPlan.FullName -Port $Port
      Stamp ("Commit result: ts_existing={0} commits={1} dry_run={2}" -f $c.ts_existing, $c.commits, $c.dry_run)
    }
  }

  Start-Sleep -Milliseconds 800
}
Stamp "Agent (plan-free) finished."
