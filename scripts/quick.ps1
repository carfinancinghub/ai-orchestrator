param(
  [ValidateSet('restart','ping','gen','stop')]$Action='ping',
  [ValidateSet('auto','app','aio_app')]$Module='auto',
  [switch]$Quiet
)

function Resolve-Module([string]$choice){
  if ($choice -and $choice -ne 'auto'){ return "$choice.server:app" }
  if (Test-Path .\app\server.py)     { return "app.server:app" }
  if (Test-Path .\aio_app\server.py) { return "aio_app.server:app" }
  throw "No server.py found in app/ or aio_app/"
}

function Stop-Aio {
  Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }
  Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force
  Get-Process python  -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ai-orchestrator*" } | Stop-Process -Force
}

function Start-Aio {
  param([string]$ModuleId)
  $venvRoot = $env:VIRTUAL_ENV
  if (-not $venvRoot -and (Test-Path .\venv\Scripts\python.exe)) { $venvRoot = (Resolve-Path ".\venv").Path }
  if (-not $venvRoot) { throw "No venv detected. Activate first: .\venv\Scripts\Activate.ps1" }
  $py = Join-Path $venvRoot "Scripts\python.exe"

  if (-not $env:AIO_PROVIDER -or $env:AIO_PROVIDER -eq "") { $env:AIO_PROVIDER = "echo" }
  if (-not $env:AIO_DRY_RUN  -or $env:AIO_DRY_RUN  -eq "") { $env:AIO_DRY_RUN  = "false" }
  $env:PYTHONUNBUFFERED = "1"

  $p = Start-Process -PassThru -FilePath $py -ArgumentList @("-m","uvicorn", $ModuleId, "--log-level","warning","--env-file",".env") -WindowStyle Hidden
  $script:AioPid = $p.Id
  if (-not $Quiet) { Write-Host "Started PID: $($p.Id)  ($ModuleId)" }
}

function Wait-Aio {
  $ok = $false
  foreach ($i in 1..40) {
    try { irm http://127.0.0.1:8000/_debug/routes | Out-Null; $ok = $true; break }
    catch { Start-Sleep -Milliseconds 200 }
  }
  if (-not $ok) { throw "Server did not start." }
}

function Ping-Aio {
  try {
    $r = irm http://127.0.0.1:8000/_debug/routes
    $s = irm http://127.0.0.1:8000/debug/settings
    if ($Quiet) {
      "OK routes=$($r.count) provider=$($s.settings.PROVIDER)"
    } else {
      "Routes: $($r.count)"; "Provider: $($s.settings.PROVIDER)"
    }
  } catch {
    if ($Quiet) { "DOWN" } else { "Server not responding" }
  }
}

function Gen-Aio {
  try {
    $null = irm -Method POST http://127.0.0.1:8000/orchestrator/run-stage/generate
    $a = irm http://127.0.0.1:8000/orchestrator/artifacts/generate
    $first = ($a.content -split "`n")[0]
    if ($Quiet) { $first } else { "Artifact: $first" }
  } catch {
    if ($Quiet) { "GEN-ERROR" } else { "Generate failed: $($_.Exception.Message)" }
  }
}

switch ($Action) {
  'stop'    { Stop-Aio; if (-not $Quiet) { "Stopped." } }
  'restart' {
    Stop-Aio
    $mod = Resolve-Module $Module
    Start-Aio -ModuleId $mod | Out-Null
    Wait-Aio
    Ping-Aio
  }
  'ping'    { Ping-Aio }
  'gen'     { Gen-Aio }
}

