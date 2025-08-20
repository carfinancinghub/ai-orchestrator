# scripts/dev.ps1 — PS 5.1–compatible helpers (hyphen names)

# Detect module (supports either folder name)
function Aio-DetectModule {
  if (Test-Path .\aio_app\server.py) { return "aio_app.server:app" }
  else                                { return "app.server:app" }
}

function Aio-Kill {
  Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force } catch {} }
  Get-Process uvicorn -ErrorAction SilentlyContinue | Stop-Process -Force
  Get-Process python  -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "*ai-orchestrator*" } | Stop-Process -Force
}

function Aio-Start {
  param([string]$Module)

  if (-not $Module -or $Module -eq "") { $Module = Aio-DetectModule }

  # venv Python
  $venvRoot = $env:VIRTUAL_ENV
  if (-not $venvRoot -and (Test-Path .\venv\Scripts\python.exe)) { $venvRoot = (Resolve-Path ".\venv").Path }
  if (-not $venvRoot) { throw "No venv detected. Activate it first (.\venv\Scripts\Activate.ps1)." }
  $venvPython = Join-Path $venvRoot "Scripts\python.exe"

  # Defaults for env if not set already
  if (-not $env:AIO_PROVIDER -or $env:AIO_PROVIDER -eq "") { $env:AIO_PROVIDER = "echo" }
  if (-not $env:AIO_DRY_RUN  -or $env:AIO_DRY_RUN  -eq "") { $env:AIO_DRY_RUN  = "false" }
  $env:PYTHONUNBUFFERED = "1"

  $p = Start-Process -PassThru -FilePath $venvPython `
       -ArgumentList @("-m","uvicorn",$Module,"--log-level","warning") `
       -WorkingDirectory (Get-Location)
  $script:AioPid = $p.Id
  Write-Host ("Started uvicorn PID: {0}  ({1})" -f $p.Id, $Module) -ForegroundColor Green
}

function Aio-Wait {
  $ok = $false
  foreach ($i in 1..60) {
    try { irm http://127.0.0.1:8000/_debug/routes | Out-Null; $ok = $true; break }
    catch { Start-Sleep -Milliseconds 250 }
  }
  if (-not $ok) { throw "Server did not start." }
}

function Aio-Restart {
  Aio-Kill
  Start-Sleep -Milliseconds 200
  Aio-Start
  Aio-Wait
}

function Aio-Ping {
  "`n/_debug/routes:";    irm http://127.0.0.1:8000/_debug/routes    | ConvertTo-Json -Depth 4
  "`n/debug/settings:";   irm http://127.0.0.1:8000/debug/settings   | ConvertTo-Json -Depth 4
}

function Aio-Gen {
  $null = irm -Method POST http://127.0.0.1:8000/orchestrator/run-stage/generate
  $art  = irm -Method GET  http://127.0.0.1:8000/orchestrator/artifacts/generate
  $first = ($art.content -split "`n")[0]
  "Artifact first line: $first"
}

function Aio-OpenDocs { start http://127.0.0.1:8000/docs }

# Optional short aliases
Set-Alias ar  Aio-Restart
Set-Alias ap  Aio-Ping
Set-Alias ag  Aio-Gen

# --- prefer app.server by default (persisted override) ---
function Aio-DetectModule {
  if (Test-Path .\app\server.py)      { return "app.server:app" }
  elseif (Test-Path .\aio_app\server.py) { return "aio_app.server:app" }
  else                                { return "app.server:app" }
}
