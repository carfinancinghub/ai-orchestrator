<#  sgman_run.ps1  — end-to-end runner for SG Man checklist
    Usage (PowerShell as Admin recommended):
      cd C:\c\ai-orchestrator\scripts\sgman_run.ps1 
	-Org "carfinancinghub" -Platform "github" 
	-Root "C:\Backup_Projects\CFH\frontend" 
	-Branches "main" 
	-Tier "wow" 
	-PreferPort 8020
#>

param(
  [string]$Org = "carfinancinghub",
  [string]$Platform = "github",
  [string]$Root = "C:\Backup_Projects\CFH\frontend",
  [string]$Branches = "main",
  [string]$Tier = "wow",
  [int]$PreferPort = 8020
)

$ErrorActionPreference = "Stop"
$PSStyle.OutputRendering = "PlainText"

# ---- Paths
$RepoRoot     = "C:\c\ai-orchestrator"
$ReportsDir   = Join-Path $RepoRoot "reports"
$ArtifactsDir = Join-Path $RepoRoot "artifacts"
$ScriptsDir   = Join-Path $RepoRoot "scripts"
$LogsDir      = Join-Path $RepoRoot "logs"
$GHWorkflow   = Join-Path $RepoRoot ".github\workflows\convert.yml"
$ServerLog    = Join-Path $LogsDir "server.log"
$RunId        = "a34f6a35" # keep aligned with SG Man example
$NowStamp     = Get-Date -Format "yyyyMMdd_HHmmss"

New-Item -ItemType Directory -Force -Path $ReportsDir,$ArtifactsDir,$ScriptsDir,$LogsDir | Out-Null

Write-Host "=== 1) Resolve Directory Structure ==="
# Remove stray folders if present (don’t fail if missing)
Remove-Item -Path (Join-Path $RepoRoot "ai-orchestrator") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -Path (Join-Path $RepoRoot "app\api") -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "=== 2) Verify Inventory Files and Outputs ==="
# List all inventory files
$inventoryList = Get-ChildItem -Path $ReportsDir -Include inventory*.txt,inventory*.list,inventory*.csv,inventory*.json,file_scan_results_*.md -Recurse -ErrorAction SilentlyContinue
if (-not $inventoryList) {
  Write-Host "No inventories found; creating sample inventory_sample.csv"
  $sample = @"
repo,branch,path
local,main,C:\Backup_Projects\CFH\frontend\src\App.jsx
local,main,C:\Backup_Projects\CFH\frontend\src\index.jsx
carfinancinghub/cfh,main,frontend/src/App.jsx
carfinancinghub/cfh,main,frontend/src/index.jsx
"@
  Set-Content -Path (Join-Path $ReportsDir "inventory_sample.csv") -Value $sample
} else {
  Write-Host "Inventories found:"; $inventoryList | Select-Object FullName, Length | Format-Table
}

# Show contents (first 20 lines) of the two example files if they exist
$tsxFullClean = Join-Path $ReportsDir 'tsx_inventory_full_clean (1).csv'
$cacheFile    = Join-Path $ReportsDir "inventory_cache_$RunId.json"
if (Test-Path $tsxFullClean) {
  Write-Host "`n--- First 20 lines of $tsxFullClean ---"
  Get-Content $tsxFullClean -TotalCount 20
} else {
  Write-Host "`n(Missing) $tsxFullClean"
}
if (Test-Path $cacheFile) {
  Write-Host "`n--- First 20 lines of $cacheFile ---"
  Get-Content $cacheFile -TotalCount 20
} else {
  Write-Host "`n(Missing) $cacheFile"
}

Write-Host "`n=== 3) Display Copilot-generated files and run outputs (if exist) ==="
$maybeFiles = @(
  "artifacts\agent_batch_20250822_091451.json",
  "artifacts\audit_js_20250822_172307.csv",
  "artifacts\convert_20250820_000305.txt",
  "artifacts\migration_list_4994e97e.csv",
  "reports\scan_$RunId.json",
  "reports\errors_$RunId.json"
) | ForEach-Object { Join-Path $RepoRoot $_ }

foreach ($f in $maybeFiles) {
  if (Test-Path $f) {
    Write-Host "`n--- $([System.IO.Path]::GetFileName($f)) ---"
    if ($f -like "*.csv") {
      Get-Content $f -TotalCount 20
    } else {
      Get-Content $f -TotalCount 20
    }
  } else {
    Write-Host "(Missing) $f"
  }
}

Write-Host "`n=== 4) Verify required files match provided versions (exist + show head) ==="
$mustFiles = @(
  "app\main.py",
  "api\routes.py",
  "app\ops.py",
  "scripts\one-prompt.ps1",
  ".github\workflows\convert.yml"
) | ForEach-Object { Join-Path $RepoRoot $_ }

foreach ($mf in $mustFiles) {
  if (Test-Path $mf) {
    Write-Host "`n--- HEAD of $mf ---"
    Get-Content $mf -TotalCount 50
  } else {
    Write-Host "(Missing) $mf"
  }
}

Write-Host "`n=== 5) Check port and run FastAPI server ==="
function Get-InUsePid {
  param([int]$Port)
  # Works on most Windows: fallback to Get-NetTCPConnection if netstat is unavailable
  $line = netstat -a -n -o | Select-String ":$Port\s"
  if ($line) {
    $pid = ($line -split "\s+")[-1]
    return [int]$pid
  }
  try {
    $conn = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
    if ($conn) { return $conn.OwningProcess }
  } catch {}
  return $null
}

$port = $PreferPort
$pid = Get-InUsePid -Port $port
if ($pid) {
  Write-Host "Port $port is busy (PID=$pid). Trying to free it..."
  try { taskkill /PID $pid /F | Out-Null } catch { Write-Host "Could not kill PID $pid: $_" }
  Start-Sleep -Seconds 2
  $pid = Get-InUsePid -Port $port
}
if ($pid) {
  # still busy; switch port
  $port = 8080
  Write-Host "Switching to port $port"
}

# Launch server (nohup-like) and capture logs
Write-Host "Starting FastAPI on port $port ..."
$py = "python"
Push-Location $RepoRoot
if (Test-Path $ServerLog) { Remove-Item $ServerLog -Force }
$serverCmd = "$py -m uvicorn app.main:app --host 127.0.0.1 --port $port"
Start-Process -FilePath "powershell" -ArgumentList "-NoProfile","-WindowStyle","Hidden","-Command","`"$serverCmd *>> `"$ServerLog`"`"" -PassThru | Out-Null
Start-Sleep -Seconds 3
Pop-Location

Write-Host "`n--- Last 30 lines of server.log ---"
if (Test-Path $ServerLog) {
  Get-Content $ServerLog -Tail 30
} else {
  Write-Host "(server.log not created yet)"
}

Write-Host "`n=== 6) Run the orchestrator (one-prompt.ps1) ==="
$onePrompt = Join-Path $ScriptsDir "one-prompt.ps1"
if (-not (Test-Path $onePrompt)) {
  Write-Host "(Missing) $onePrompt — cannot run conversion trigger."
} else {
  & $onePrompt -PromptKey convert -Tier $Tier -Root $Root -Port $port -Org $Org -Platform $Platform -Branches $Branches -TriggerWorkflow
}

Write-Host "`n=== 7) Snapshot key outputs (if created) ==="
$scanJson = Join-Path $ReportsDir "scan_$RunId.json"
$errorsJson = Join-Path $ReportsDir "errors_$RunId.json"
if (Test-Path $scanJson)   { Write-Host "`n--- First 20 lines of scan_$RunId.json ---";   Get-Content $scanJson -TotalCount 20 }
if (Test-Path $errorsJson) { Write-Host "`n--- First 20 lines of errors_$RunId.json ---"; Get-Content $errorsJson -TotalCount 20 }

Write-Host "`n=== DONE ==="
Write-Host "Port used: $port"
Write-Host "Server log: $ServerLog"
Write-Host "Reports dir: $ReportsDir"
Write-Host "Artifacts dir: $ArtifactsDir"
