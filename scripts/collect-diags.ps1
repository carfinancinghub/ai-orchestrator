param([int]$Port=8010)

Write-Host "== Orchestrator diagnostics ==" -ForegroundColor Cyan
Write-Host "[*] Location: $((Get-Location).Path)"
Write-Host "[*] Python:   $(python -V 2>$null)"
Write-Host "[*] FastAPI:  $(python -c "import fastapi; print(fastapi.__version__)" 2>$null)"
Write-Host "[*] Uvicorn:  $(python -c "import uvicorn; print(uvicorn.__version__)" 2>$null)"

# Port check
try{
  $tcp = Get-NetTCPConnection -LocalPort $Port -ErrorAction Stop | Select-Object -First 1
  if($tcp){
    $proc = Get-Process -Id $tcp.OwningProcess -ErrorAction SilentlyContinue
    Write-Host "[*] Port ${Port}: LISTENING (PID=$($tcp.OwningProcess) $($proc.ProcessName))" -ForegroundColor Green
  }
}catch{
  Write-Host "[*] Port ${Port}: free" -ForegroundColor Yellow
}

# Health
try{
  $h = Invoke-RestMethod -Uri "http://127.0.0.1:${Port}/health" -TimeoutSec 2
  Write-Host "[*] Health: $($h | ConvertTo-Json -Depth 3)" -ForegroundColor Green
}catch{
  Write-Host "[*] Health: unreachable" -ForegroundColor Yellow
}

# Artifacts
Write-Host "`n== artifacts (most recent) ==" -ForegroundColor Cyan
Get-ChildItem .\artifacts -File -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 10 |
  Format-Table LastWriteTime, Length, Name -AutoSize

Write-Host "`n== tail (*.txt) ==" -ForegroundColor Cyan
Get-ChildItem .\artifacts -Filter *.txt -ErrorAction SilentlyContinue |
  Sort-Object LastWriteTime -Descending | Select-Object -First 3 |
  ForEach-Object {
    Write-Host "`n--- $($_.Name) ---"
    Get-Content $_.FullName -Tail 60
  }
