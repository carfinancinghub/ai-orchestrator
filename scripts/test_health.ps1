param(
  [string]$Host = "127.0.0.1",
  [int]$Port = 8121
)

Write-Host "Starting uvicorn..."
$env:HOST=$Host
$env:PORT=$Port
$env:LOG_LEVEL="INFO"

Start-Process -PassThru -WindowStyle Hidden powershell -ArgumentList @("-NoProfile","-Command","python -m uvicorn --factory app.server:create_app --host $Host --port $Port") | Out-Null
Start-Sleep -Seconds 2

try {
  $ready = Invoke-RestMethod "http://$Host:$Port/readyz"
  Write-Host "readyz ok: $($ready.ok)"
  $self = Invoke-RestMethod "http://$Host:$Port/providers/selftest"
  Write-Host "providers selftest:" ($self | ConvertTo-Json -Depth 5)
  $body = @{ root="src"; dry_run=$true; batch_cap=2 } | ConvertTo-Json
  $r = Invoke-RestMethod -Method POST -Uri "http://$Host:$Port/convert/tree" -ContentType 'application/json' -Body $body
  Write-Host "convert ok: $($r.ok) summary: $($r.summary)"
  exit 0
} catch {
  Write-Error $_
  exit 1
}
