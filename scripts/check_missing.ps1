param([string]$FeedPath = ".\reports\conversion_candidates.txt")
$feed    = Get-Content $FeedPath -ErrorAction SilentlyContinue | Where-Object { $_ }
$missing = $feed | Where-Object { -not (Test-Path $_) }
$missing | Set-Content ".\reports\feed_missing_local.txt" -Encoding UTF8
Write-Host ("Missing: {0}" -f (($missing | Where-Object { $_ }).Count))
Write-Host "-> reports\feed_missing_local.txt"
