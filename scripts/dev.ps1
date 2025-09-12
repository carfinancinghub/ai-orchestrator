# scripts/dev.ps1
Set-StrictMode -Version Latest

# --- Paths & setup -----------------------------------------------------------
$global:Root   = (Resolve-Path .).Path
$global:LogDir = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $global:LogDir | Out-Null
$global:PY     = Join-Path $Root ".venv\Scripts\python.exe"

function Use-Py {
  param([string]$RootPath = $global:Root)
  $global:Root = (Resolve-Path $RootPath).Path
  $global:LogDir = Join-Path $global:Root "logs"
  New-Item -ItemType Directory -Force -Path $global:LogDir | Out-Null
  $global:PY   = Join-Path $global:Root ".venv\Scripts\python.exe"
  if (!(Test-Path $global:PY)) { throw "Python venv not found at $global:PY" }
  & $global:PY -V
}

# --- Log helpers --------------------------------------------------------------
function New-LogPath {
  param([Parameter(Mandatory)][string]$Name)
  $ts  = Get-Date -Format "yyyyMMdd-HHmmss"
  $log = Join-Path $global:LogDir "$Name-$ts.log"
  # remember "latest" for this logical name
  Set-Content (Join-Path $global:LogDir "$Name.latest") $log
  return $log
}

function Get-LogPath {
  param([Parameter(Mandatory)][string]$Name)
  $latest = Join-Path $global:LogDir "$Name.latest"
  if (Test-Path $latest) { return (Get-Content $latest) }
  # fall back to most recent matching file
  $f = Get-ChildItem $global:LogDir -Filter "$Name-*.log" -File -ErrorAction SilentlyContinue |
       Sort-Object LastWriteTime -Descending | Select-Object -First 1
  if ($f) { return $f.FullName }
  throw "No logs found for name '$Name'."
}

function List-Logs {
  Get-ChildItem $global:LogDir -Filter "*.log" -File |
    Sort-Object LastWriteTime -Descending |
    Select-Object LastWriteTime, Length,
                  @{n="Name";e={$_.BaseName}},
                  @{n="Path";e={$_.FullName}} | Format-Table -AutoSize
}

function Tail-Log {
  param(
    [Parameter(Mandatory)][string]$Name,
    [int]$Lines = 100
  )
  $path = Get-LogPath $Name
  Write-Host "Tailing $path"
  Get-Content -Wait -Tail $Lines $path
}

function Share-Log {
  param(
    [Parameter(Mandatory)][string]$Name,
    [string]$OutDir = (Join-Path $global:Root "reports")
  )
  $src = Get-LogPath $Name
  New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
  $dst = Join-Path $OutDir (Split-Path $src -Leaf)
  Copy-Item $src $dst -Force
  Write-Host "Copied to $dst"
  return $dst
}

function Find-Errors {
  param(
    [Parameter(Mandatory)][string]$Name,
    [int]$ContextAfter = 3
  )
  $path = Get-LogPath $Name
  Write-Host "Scanning $path for errors…"
  # quick regex: pytest "E   ", ERROR/Exception/Traceback lines
  Select-String -Path $path -Pattern '^(E +|ERROR|Error|Exception|Traceback|AssertionError)' -Context 0,$ContextAfter
}

# --- Logged invoker (timestamped file + .latest pointer) ---------------------
function Invoke-Logged {
  param(
    [Parameter(Mandatory)] [string]      $Name,
    [Parameter(Mandatory)] [scriptblock] $Script
  )
  $log = New-LogPath $Name
  Write-Host "→ logging to $log"
  & $Script 2>&1 | Tee-Object -FilePath $log
  Write-Host "✔ done: $log"
  return $log
}

# --- Server: start/stop/tail -------------------------------------------------
function Start-Server {
  param([int]$Port = 8000)
  if (!(Test-Path $global:PY)) { throw "Python venv not found at $global:PY" }

  if (Test-Path ".server.pid") {
    Write-Host "server already running (pid $(Get-Content .server.pid))"
    return
  }

  $log = New-LogPath "server"
  $args = @(
    "-m","uvicorn","app.server:app",
    "--host","127.0.0.1","--port",$Port,
    "--reload",
    "--reload-exclude",".venv/*",
    "--reload-exclude",".venv\*",
    "--reload-exclude","logs/*",
    "--reload-exclude","artifacts/*"
  )
  # NOTE: Using -Redirect* writes continuously to $log; tail with Tail-Server.
  $p = Start-Process -FilePath $global:PY `
                     -ArgumentList $args `
                     -RedirectStandardOutput $log `
                     -RedirectStandardError  $log `
                     -PassThru `
                     -WorkingDirectory $global:Root
  $p.Id | Set-Content ".server.pid"
  Write-Host "server started pid=$($p.Id); log=$log"
}

function Stop-Server {
  if (Test-Path ".server.pid") {
    $pid = Get-Content ".server.pid"
    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
    Remove-Item ".server.pid" -Force
    Write-Host "server stopped"
  } else {
    Write-Host "no server.pid — nothing to stop"
  }
}

function Tail-Server { Tail-Log -Name "server" -Lines 200 }

# --- Common tasks (logged) ---------------------------------------------------
function Pip-Install { Invoke-Logged "pip_install" { & $global:PY -m pip install -r requirements.txt } }
function Test-All    { Invoke-Logged "pytest"      { & $global:PY -m pytest -q } }
function Lint-Fix    { Invoke-Logged "ruff_fix"    { & $global:PY -m ruff check . --fix } }

# --- Rebuild venv safely (stops server first) --------------------------------
function Rebuild-Venv {
  Stop-Server
  if (Test-Path ".venv") {
    try {
      # Some .pyd files may be locked by a running python; ensure no processes first.
      Remove-Item -Recurse -Force ".venv"
    } catch {
      throw "Close any processes using .venv (python/uvicorn/shells), then retry. $_"
    }
  }
  py -3.13 -m venv .venv
  $global:PY = Join-Path $global:Root ".venv\Scripts\python.exe"
  & $global:PY -m pip install -U pip
  if (Test-Path "requirements.txt") { & $global:PY -m pip install -r requirements.txt }
  Write-Host "venv rebuilt."
}
