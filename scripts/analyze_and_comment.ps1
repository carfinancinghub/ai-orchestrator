param(
  [string]$FrontPath = $env:FRONTEND_PATH,
  [string]$Stamp     = $env:stamp
)
$ErrorActionPreference = "Stop"

function Get-FrontStamp([string]$Path) {
  try {
    $cur = git -C $Path branch --show-current 2>$null
    if ($cur -and $cur -match '^ts-migration/(.+)$') { return $Matches[1] }
  } catch {}
  return $null
}

if (-not $FrontPath -or -not (Test-Path $FrontPath)) { throw "Frontend path missing." }
if (-not $Stamp) { $Stamp = Get-FrontStamp $FrontPath }
if (-not $Stamp) { throw "No stamp available (need ts-migration/<stamp>)." }

$env:FRONTEND_PATH = $FrontPath
$env:stamp         = $Stamp

# 1) Run analyzer (writes report.md + plan.json under reports/analysis/<stamp>)
node "$PSScriptRoot\..\app\analyze-frontend.mjs"

# 2) Post report to the PR for ts-migration/<stamp> and add labels
$fNum = gh pr view -R carfinancinghub/cfh "ts-migration/$Stamp" --json number -q .number 2>$null
if (-not $fNum) {
  # Create the PR if it doesn't exist yet
  gh pr create -R carfinancinghub/cfh --base main --head "ts-migration/$Stamp" `
    --title "TS migration: $Stamp" `
    --body "Automated PR for TS migration batch $Stamp.`n`nGates log: https://github.com/carfinancinghub/cfh/blob/ts-migration/$Stamp/reports/debug/frontend_build_test_lint_$Stamp.md" | Out-Null
  $fNum = gh pr view -R carfinancinghub/cfh "ts-migration/$Stamp" --json number -q .number
}

$report = Get-ChildItem "$PSScriptRoot\..\reports\analysis\$Stamp\report.md"
gh pr comment -R carfinancinghub/cfh $fNum -F $report.FullName

# Ensure labels exist, then apply
gh label create ts-migration -R carfinancinghub/cfh --color FFD966 --description "TypeScript migration" 2>$null
gh label create analysis      -R carfinancinghub/cfh --color B6D7A8 --description "Automated analyzer report" 2>$null
gh pr edit -R carfinancinghub/cfh $fNum --add-label "ts-migration" --add-label "analysis"

Write-Host "Updated PR: https://github.com/carfinancinghub/cfh/pull/$fNum"
