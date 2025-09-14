param(
  [Parameter(Mandatory=$true)][string]$Name,
  [Parameter(Mandatory=$true)][string]$Command,
  [string]$Cwd = "C:\c\ai-orchestrator",
  [string]$BranchPrefix = "logs"
)

$ErrorActionPreference = 'Stop'
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$branch = "$BranchPrefix/$Name-$ts"
$logDir = Join-Path $Cwd "reports\logs\$Name"
$logFile = Join-Path $logDir "$Name-$ts.log"
$newline = [System.Environment]::NewLine

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Push-Location $Cwd
try {
  git switch -c $branch

  "`n=== RUN @ $ts ===`n" | Out-File -FilePath $logFile -Encoding UTF8
  "CWD: $Cwd`nCMD: $Command`n" | Out-File -FilePath $logFile -Encoding UTF8 -Append

  # capture stdout+stderr
  $start = Get-Date
  "----- OUTPUT BEGIN -----`n" | Out-File -FilePath $logFile -Encoding UTF8 -Append
  & powershell -NoProfile -ExecutionPolicy Bypass -Command $Command 2>&1 | Tee-Object -FilePath $logFile -Append | Out-Null
  "----- OUTPUT END -----`n"   | Out-File -FilePath $logFile -Encoding UTF8 -Append
  $dur = (Get-Date) - $start
  "DURATION: $($dur.ToString())`n" | Out-File -FilePath $logFile -Encoding UTF8 -Append

  git add $logFile
  git commit -m "logs($Name): $ts"
  git push -u origin $branch

  $remote = git remote get-url origin
  "Branch pushed: $branch"
  "Log file: reports/logs/$Name/$([IO.Path]::GetFileName($logFile))"
  "Open PR: https://github.com/carfinancinghub/ai-orchestrator/pull/new/$branch"
}
finally {
  Pop-Location
}
