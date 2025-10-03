
# scripts\orchestrator-smoke.ps1
# Simple smoke test for your local ai-orchestrator

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$base = "http://127.0.0.1:8021"

Write-Host "== Orchestrator Smoke ==" -ForegroundColor Cyan

# _health
try {
  $h = Invoke-RestMethod -Method GET -Uri "$base/_health" -TimeoutSec 5
  Write-Host ("health: {0}" -f ($h | ConvertTo-Json -Depth 5))
} catch {
  Write-Host "health: FAIL $_" -ForegroundColor Red
}

# providers/list
$provider = $null
$model    = $null
try {
  $p = Invoke-RestMethod -Method GET -Uri "$base/providers/list" -TimeoutSec 5
  Write-Host ("providers: {0}" -f ($p | ConvertTo-Json -Depth 5))
  $preferred = @("openai","grok","google","anthropic")
  $provider  = ($preferred | Where-Object { $_ -in $p.PSObject.Properties.Name -and $p.$_ -eq $true } | Select-Object -First 1)
  if (-not $provider) { $provider = "openai" } # default fallback
  $model = if ($provider -eq "openai") { "gpt-4o-mini" }
           elseif ($provider -eq "grok") { "grok-2-latest" }
           elseif ($provider -eq "google") { "gemini-1.5-pro" }
           else { "gpt-4o-mini" }
  Write-Host ("Using provider: {0}   model: {1}" -f $provider,$model) -ForegroundColor Cyan
} catch {
  Write-Host "providers: FAIL $_" -ForegroundColor Red
  $provider = "openai"
  $model    = "gpt-4o-mini"
}

# convert/tree dry-run
$body = @{
  root     = "C:\CFH\frontend\src\components"
  provider = $provider
  model    = $model
  dry_run  = $true
  limit    = 5
} | ConvertTo-Json -Compress

try {
  $r = Invoke-RestMethod -Method POST -Uri "$base/convert/tree" -ContentType 'application/json' -Body $body -TimeoutSec 60
  Write-Host ("convert/tree dry-run: {0}" -f ($r | ConvertTo-Json -Depth 6))
} catch {
  Write-Host "convert/tree dry-run: FAIL $_" -ForegroundColor Red
}

