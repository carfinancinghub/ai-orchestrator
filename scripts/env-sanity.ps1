# scripts\env-sanity.ps1
# Clears conflicting env vars, shows current vars, and pings /providers/list.

param(
  [string]$ServerBase = "http://127.0.0.1:8021"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "== Clearing conflicting environment variables (Process) ==" -ForegroundColor Cyan
$varsToClear = @(
  "AIO_LIVE_AI","AIO_LIVE_AI_VENDOR",
  "OPENAI_API_KEY","GROK_API_KEY","XAI_GROK_API_KEY","XAI_API_KEY",
  "GOOGLE_API_KEY","GEMINI_API_KEY"
)
foreach ($v in $varsToClear) { Remove-Item "Env:$v" -ErrorAction SilentlyContinue }

Write-Host "== Reminder ==" -ForegroundColor Yellow
Write-Host "If you previously set USER/MACHINE env vars, clear them too (optional):"
Write-Host '  [Environment]::SetEnvironmentVariable("OPENAI_API_KEY",$null,"User")'
Write-Host '  [Environment]::SetEnvironmentVariable("OPENAI_API_KEY",$null,"Machine")'
Write-Host ""

Write-Host "== Preview of .env on disk (first 4 non-comment lines) ==" -ForegroundColor Cyan
$envPath = "C:\c\ai-orchestrator\.env"
if (Test-Path $envPath) {
  Get-Content $envPath | Where-Object {$_ -notmatch '^\s*#' -and $_ -match '='} | Select-Object -First 4
} else {
  Write-Host "No .env found at $envPath" -ForegroundColor Red
}

Write-Host "`n== IMPORTANT ==" -ForegroundColor Yellow
Write-Host "Restart Uvicorn so the server reloads .env cleanly:"
Write-Host "  Ctrl+C in the uvicorn window, then:"
Write-Host "  uvicorn app.server:create_app --factory --host 127.0.0.1 --port 8021 --reload"
Write-Host ""

try {
  Write-Host "== providers/list (after restart) ==" -ForegroundColor Cyan
  $p = Invoke-RestMethod -Uri "$ServerBase/providers/list" -Method GET -TimeoutSec 5
  $p | ConvertTo-Json -Depth 5
} catch {
  Write-Host "providers/list failed (is the server running?): $($_.Exception.Message)" -ForegroundColor Red
}
