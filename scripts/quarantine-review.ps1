<#
  File: scripts/quarantine-review.ps1
  Purpose: Quick helpers to list & (optionally) restore quarantined files the API recorded.
  Usage:
    # List last 50 quarantined items
    ./scripts/quarantine-review.ps1 -Port 8010 -List -Limit 50

    # Restore one or more quarantine paths (as printed by -List)
    ./scripts/quarantine-review.ps1 -Port 8010 -Restore @("artifacts\quarantine\20250822\missing\foo.js") -Overwrite:$false
#>

param(
  [int]$Port = 8010,
  [switch]$List,
  [int]$Limit = 50,
  [string[]]$Restore = @(),
  [switch]$Overwrite = $false
)

$ErrorActionPreference = 'Stop'
function Stamp { param([string]$m) Write-Host ("[{0}] {1}" -f (Get-Date -Format HH:mm:ss), $m) }

if ($List) {
  Stamp "Listing quarantine items ..."
  $resp = Invoke-RestMethod "http://127.0.0.1:$Port/audit/js/quarantine/list?limit=$Limit"
  $resp.items | Select-Object when_utc,reason,dest,src | Format-Table -AutoSize
  return
}

if ($Restore.Count -gt 0) {
  Stamp "Restoring $($Restore.Count) item(s) ..."
  $body = @{ dest_paths = $Restore; overwrite = [bool]$Overwrite } | ConvertTo-Json
  $resp = Invoke-RestMethod -Method POST "http://127.0.0.1:$Port/audit/js/quarantine/restore" -ContentType 'application/json' -Body $body
  "Restored:"; $resp.restored | Format-Table -AutoSize
  "Skipped:";  $resp.skipped  | Format-Table -AutoSize
  return
}

Write-Host "Nothing to do. Use -List or -Restore."
