param(
  [int]$Port = 8020,
  [string]$Root = "C:\c\ai-orchestrator"
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

function Is-Listening([int]$p){
  try { $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue; return $null -ne $c }
  catch { return $false }
}

if (Is-Listening -p $Port) {
  Write-Host "Port $Port already in use. Not starting another server."
  exit 0
}

Set-Location $Root
# Start uvicorn detached; do NOT kill anything else.
Start-Process python -ArgumentList @('-m','uvicorn','app.main:app','--app-dir','.', '--host','127.0.0.1','--port',"$Port") -WorkingDirectory (Get-Location) | Out-Null
Start-Sleep -Seconds 1
try {
  $resp = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:$Port/health" -TimeoutSec 3
  "Started on :$Port; health: $($resp.StatusCode) $($resp.Content)"
} catch {
  "Started process for :$Port, but /health check failed: $_"
}
