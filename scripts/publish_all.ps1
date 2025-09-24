# scripts/publish_all.ps1
param(
  [string]$FrontRepoPath = "C:\Backup_Projects\CFH\frontend",
  [string]$OrchRepoPath  = "C:\c\ai-orchestrator"
)

$ErrorActionPreference = 'Stop'

function In-Repo { param($Path,$Script) Push-Location $Path; try { & $Script } finally { Pop-Location } }

# 0) Stamp (shared)
if (-not $env:stamp -or -not $env:stamp.Trim()) { $env:stamp = Get-Date -Format yyyyMMdd_HHmmss }
$stamp = $env:stamp
$repos = @($FrontRepoPath, $OrchRepoPath)
foreach ($r in $repos) {
  $dir = Join-Path $r ".orchestrator"
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Set-Content (Join-Path $dir "stamp.txt") $stamp -Encoding UTF8
}

# 1) Frontend gates (build / test / lint) → write stamped log and commit
In-Repo $FrontRepoPath {
  $frontHead = "ts-migration/$stamp"
  git checkout -B $frontHead

  $log = "reports\debug\frontend_build_test_lint_$stamp.md"
  New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

  # Build/test/lint – uses our safe Vitest launcher & eslint config
  (npm run build)    *>> $log
  (npm run test:ci)  *>> $log
  (npm run lint)     *>> $log

  git add $log package.json package-lock.json tests/ vitest.config.ts .gitignore scripts/run-vitest.ps1
  git commit -m "gates(frontend): build/test/lint [$stamp]" 2>$null | Out-Null
  git push -u origin $frontHead
}

# 2) Create/find PRs & stamp summary links
In-Repo $OrchRepoPath {
  if (-not (Test-Path .\scripts\publish_compat.ps1)) {
    throw "scripts/publish_compat.ps1 not found; add it first."
  }
  pwsh -NoProfile -ExecutionPolicy Bypass -File .\scripts\publish_compat.ps1 | Out-Null
  Write-Host "`nSummary URL:"
  Write-Host ("https://github.com/carfinancinghub/ai-orchestrator/blob/fix/restore-report-docs/reports/debug/summary_links_{0}.md" -f $stamp)
}
