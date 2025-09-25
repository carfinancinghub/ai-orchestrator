# Produce reports\gates_20250923_2212.json from the three gates
Param([string]$RunId = "20250923_2212")
$ErrorActionPreference = "Stop"
$report = Join-Path (Resolve-Path ".") "reports\gates_$RunId.json"

$vendor = "unknown"; $nojs = "unknown"; $tsc = "unknown"

try { pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\check-no-vendor.ps1; $vendor = "pass" } catch { $vendor = "fail" }
try { pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\check-no-js.ps1;     $nojs  = "pass" } catch { $nojs  = "fail" }

$env:CFH_LINT_SOFT="0"
try {
  pwsh -NoProfile -ExecutionPolicy Bypass -File scripts\cfh_lint.ps1
  $sum = Get-Content .\reports\cfh_lint_summary.json -Raw | ConvertFrom-Json
  $tsc = $sum.tsc
} catch {
  $tsc = "error"
}

@{ runId=$RunId; vendor=$vendor; no_js=$nojs; cfh_lint=$tsc } |
  ConvertTo-Json -Depth 4 | Set-Content -Encoding UTF8 $report

Write-Host "Gates report → $report"
