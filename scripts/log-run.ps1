param(
  [Parameter(Mandatory=$true)][ScriptBlock]$Do,
  [string]$Label = "run",
  [switch]$NoGit
)

$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logsDir = "reports\logs"
New-Item -ItemType Directory -Force -Path $logsDir | Out-Null
$logFile = Join-Path $logsDir ("session_{0}_{1}.log" -f $Label,$stamp)

$ErrorActionPreference = "Stop"
$sw = [System.Diagnostics.Stopwatch]::StartNew()
try {
  & $Do *>&1 | Tee-Object -FilePath $logFile
  $status = "ok"
} catch {
  $_ | Tee-Object -FilePath $logFile
  $status = "error"
} finally {
  $sw.Stop()
}

Write-Host ("Session log (raw): {0}/reports/logs/{1}" -f "https://raw.githubusercontent.com/carfinancinghub/ai-orchestrator/$(git rev-parse --abbrev-ref HEAD)", (Split-Path $logFile -Leaf))

if (-not $NoGit) {
  git add $logFile
  git commit -m ("chore(logs): {0} ({1}s)" -f $Label, [int]$sw.Elapsed.TotalSeconds) | Out-Null
  git push | Out-Null
}
