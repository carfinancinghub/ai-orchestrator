<#
  File: scripts/quarantine-review.ps1
  Purpose: Inspect and optionally restore quarantined items created by the auditor.
  Usage:
    # list last 50
    ./scripts/quarantine-review.ps1 -List -Limit 50
    # restore by exact path(s)
    ./scripts/quarantine-review.ps1 -Restore -Paths "C:\Backup_Projects\CFH\path\to\bad.js"
    # restore by glob under quarantine folder
    ./scripts/quarantine-review.ps1 -Restore -Glob "artifacts\quarantine\**\*.js"
#>

param(
  [switch]$List,
  [int]$Limit = 50,
  [switch]$Restore,
  [string[]]$Paths = @(),
  [string]$Glob = ""
)

$ErrorActionPreference = 'Stop'

if ($List) {
  irm "http://127.0.0.1:8010/audit/js/quarantine/list?limit=$Limit"
  exit 0
}

if ($Restore) {
  $destPaths = @()
  if ($Paths.Count -gt 0) { $destPaths += $Paths }
  if ($Glob -ne "") {
    $matches = Get-ChildItem -File -Recurse $Glob | % { $_.FullName }
    $destPaths += $matches
  }
  if ($destPaths.Count -eq 0) { Write-Error "Nothing to restore. Provide -Paths or -Glob."; exit 1 }

  irm -Method POST "http://127.0.0.1:8010/audit/js/quarantine/restore" `
    -ContentType 'application/json' `
    -Body (@{ dest_paths = $destPaths; overwrite = $false } | ConvertTo-Json)
}
