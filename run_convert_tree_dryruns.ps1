# Auto-generated: call /convert/tree dry-runs per root
param(
  [string]$ApiHost = $env:HOST
, [int]$ApiPort    = [int]($env:PORT)
)

if (-not $ApiHost) { $ApiHost = "127.0.0.1" }
if (-not $ApiPort) { $ApiPort = 8121 }

$base = "http://$ApiHost`:$ApiPort"
Write-Host "Posting to $base/convert/tree" -ForegroundColor Cyan

$roots = @(
  "C:\Backup_Projects"
  "C:\CFH\TruthSource"
  "C:\CFH\backend"
  "C:\CFH\docs"
  "C:\CFH\frontend"
  "M:\cfh"
)

foreach ($r in $roots) {
  $payload = @{ root = $r; dry_run = $true } | ConvertTo-Json -Compress
  try {
    $resp = Invoke-RestMethod -Method POST -Uri "$base/convert/tree" -ContentType "application/json" -Body $payload
    $ok = if ($resp.ok) { "OK" } else { "ERR" }
    "{0} {1} (converted={2}, skipped={3})" -f $ok, $r, ($resp.converted | Measure-Object | % Count), ($resp.skipped | Measure-Object | % Count)
  } catch {
    "ERR {0}: $($_.Exception.Message)" -f $r
  }
}

