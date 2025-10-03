# scripts/ports.ps1

function Show-Port {
  param([int]$Port)

  $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
  if (-not $conns) {
    Write-Host ("Port $($Port): nothing listening.") -ForegroundColor Green
    return
  }

  $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
  Write-Host ("Port $($Port) listeners:") -ForegroundColor Cyan

  foreach ($id in $procIds) {
    try {
      $p = Get-Process -Id $id -ErrorAction Stop
      $name = $p.ProcessName
      $path = $p.Path
      Write-Host ("  PID {0}  Name {1}  Path {2}" -f $id,$name,$path)
    } catch {
      Write-Host ("  PID {0}  (no process info)" -f $id)
    }
  }
}

function Free-Port {
  param(
    [int]$Port,
    [int]$MaxAttempts = 6,
    [int]$SleepMs = 700
  )

  for ($i = 1; $i -le $MaxAttempts; $i++) {
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $conns) {
      Write-Host ("Port $($Port) is free.") -ForegroundColor Green
      return
    }

    $procIds = $conns | Select-Object -ExpandProperty OwningProcess -Unique
    Write-Host ("Attempt {0}/{1}: terminating listeners for port {2} ..." -f $i,$MaxAttempts,$Port) -ForegroundColor Yellow

    foreach ($id in $procIds) {
      # Kill the entire process tree (reloader + worker, etc.)
      try {
        Start-Process -FilePath "taskkill.exe" -ArgumentList "/PID $id /F /T" -NoNewWindow -Wait
      } catch {
        # Fallback
        try { Stop-Process -Id $id -Force -ErrorAction Stop } catch {}
      }
    }

    Start-Sleep -Milliseconds $SleepMs

    $still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $still) {
      Write-Host ("Port $($Port) is free.") -ForegroundColor Green
      return
    } else {
      Write-Host ("Port $($Port) still in use; will retry...") -ForegroundColor Yellow
      Show-Port -Port $Port
    }
  }

  Write-Host ("Gave up after {0} attempts. Something keeps respawning on port {1}." -f $MaxAttempts,$Port) -ForegroundColor Red
  Write-Host "Tip: if it's uvicorn with --reload, stop that window first, or kill the parent (reloader) PID." -ForegroundColor DarkYellow
}
