# Append a single line to reports/wave_metrics_redis.csv from /redis/health
try {
  $resp = Invoke-RestMethod http://127.0.0.1:8121/redis/health -Method GET -ErrorAction Stop
  $ts = $resp.ts
  $enabled = [int]($resp.enabled -eq $true)
  $reachable = [int]($resp.reachable -eq $true)
  $line = '"' + $ts + '","redis","' + $enabled + '","' + $reachable + '"'
  $out = "reports/wave_metrics_redis.csv"
  if (!(Test-Path $out)) {
    'ts,module,enabled,reachable' | Set-Content -Path $out -Encoding UTF8
  }
  Add-Content -Path $out -Value $line
} catch {
  $ts = (Get-Date).ToUniversalTime().ToString("s") + "Z"
  $line = '"' + $ts + '","redis","err","err"'
  $out = "reports/wave_metrics_redis.csv"
  if (!(Test-Path $out)) {
    'ts,module,enabled,reachable' | Set-Content -Path $out -Encoding UTF8
  }
  Add-Content -Path $out -Value $line
}