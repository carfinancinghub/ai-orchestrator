# C:\c\ai-orchestrator\scripts\audit-ts.ps1
# Audit TS/TSX vs JS/JSX coverage in the repo (with heavy-folder excludes).
# Writes a summary and CSV inventories under reports/audit-ts/<timestamp>.

[CmdletBinding()]
param(
  [string]$Root = "C:\c\ai-orchestrator"
)

$ErrorActionPreference = "Stop"

$Stamp   = (Get-Date).ToString("yyyyMMdd_HHmmss")
$OutDir  = Join-Path $Root "reports\audit-ts\$Stamp"
$SumFile = Join-Path $OutDir "summary.md"
$TsCsv   = Join-Path $OutDir "ts_inventory.csv"
$JsCsv   = Join-Path $OutDir "js_inventory.csv"

# Same excludes as discovery (including .mypy_cache and logs)
$ExcludePattern = '\\node_modules\\|\\\.venv\\|\\venv\\|\\dist\\|\\build\\|\\\.git\\|\\__pycache__\\|\\\.next\\|\\coverage\\|\\out\\|\\release\\|\\tmp\\|\\temp\\|\\\.mypy_cache\\|\\logs\\'

function Ensure-Dir([string]$p) {
  if (-not (Test-Path -LiteralPath $p)) { New-Item -ItemType Directory -Force -Path $p | Out-Null }
}
function Is-Excluded([string]$full) { return ($full -match $ExcludePattern) }

Write-Host "Auditing $Root ..." -ForegroundColor Cyan
Ensure-Dir $OutDir

# Gather files
Write-Host "Scanning filesystem (excludes applied)..." -ForegroundColor Yellow
$all = Get-ChildItem -Path $Root -Recurse -File -ErrorAction SilentlyContinue |
  Where-Object { -not (Is-Excluded $_.FullName) }

# Classify
$ts  = $all | Where-Object { $_.Extension -match '^\.(ts|tsx)$' } | Select FullName, Length, LastWriteTime
$js  = $all | Where-Object { $_.Extension -match '^\.(js|jsx)$' } | Select FullName, Length, LastWriteTime

# Write CSVs
$ts | Sort-Object FullName | Export-Csv -LiteralPath $TsCsv -NoTypeInformation -Encoding UTF8
$js | Sort-Object FullName | Export-Csv -LiteralPath $JsCsv -NoTypeInformation -Encoding UTF8

# Summary
$lines = New-Object System.Collections.Generic.List[string]
$lines.Add("# TypeScript Audit")
$lines.Add("")
$lines.Add("**Timestamp:** $Stamp  ")
$lines.Add("**Root:** $Root  ")
$lines.Add("")
$lines.Add("## Totals")
$lines.Add( ("- .ts/.tsx files: {0}" -f ($ts.Count)) )
$lines.Add( ("- .js/.jsx files: {0}" -f ($js.Count)) )
$lines.Add("")
$lines.Add("## Examples (first 20 JS/JSX)")
$lines.Add("")
$js | Select-Object -First 20 |
  ForEach-Object { $lines.Add("- " + $_.FullName) }
$lines.Add("")
$lines.Add("## Artifacts")
$lines.Add("")
$lines.Add("```text")
$lines.Add($TsCsv)
$lines.Add($JsCsv)
$lines.Add("```")
$lines | Set-Content -LiteralPath $SumFile -Encoding UTF8

Write-Host "`n=== Artifacts ===" -ForegroundColor Green
Write-Host $TsCsv
Write-Host $JsCsv
Write-Host $SumFile
Write-Host "================="

Write-Host "Audit complete." -ForegroundColor Green
