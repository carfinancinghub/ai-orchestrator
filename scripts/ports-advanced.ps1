# C:\c\ai-orchestrator\scripts\ports-advanced.ps1
# Helpers to inspect and free Windows ports cleanly (works around $PID conflicts)

Set-StrictMode -Version Latest

function Get-PortListeners {
  param([Parameter(Mandatory)][int]$Port)
  Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
}

function Get-ProcInfo {
  param([int]$ProcId)
  try {
    $p = Get-CimInstance Win32_Process -Filter "ProcessId=$ProcId"
    if ($null -eq $p) { return @{ ProcId=$ProcId; Name='(no process)'; Parent=$null; CommandLine='(n/a)' } }
    return @{
      ProcId      = $p.ProcessId
      Name        = $p.Name
      Parent      = $p.ParentProcessId
      CommandLine = ($p.CommandLine ?? '(n/a)')
    }
  } catch {
    return @{ ProcId=$ProcId; Name='(no process)'; Parent=$null; CommandLine='(n/a)' }
  }
}

function Show-Port {
  param([Parameter(Mandatory)][int]$Port)
  $procs = Get-PortListeners -Port $Port
  if (-not $procs) {
    Write-Host ("Port {0}: nothing listening." -f $Port) -ForegroundColor Green
    return
  }
  Write-Host ("Port {0} listeners:" -f $Port) -ForegroundColor Cyan
  foreach ($procId in $procs) {
    $info = Get-ProcInfo -ProcId $procId
    "{0}  {1}" -f $info.ProcId, ($info.CommandLine -replace '\s+', ' ').Substring(0, [Math]::Min(120, ($info.CommandLine).Length))
  }
}

function Port-Diag {
  param([Parameter(Mandatory)][int]$Port)
  $procs = Get-PortListeners -Port $Port
  if (-not $procs) {
    Write-Host ("Port {0}: nothing listening." -f $Port) -ForegroundColor Green
    return
  }
  # Pick the first PID and walk up to find the root parent
  $cur = $procs | Select-Object -First 1
  $chain = @()
  while ($cur) {
    $info = Get-ProcInfo -ProcId $cur
    $chain += $info
    if (-not $info.Parent -or $info.Parent -eq 0 -or $info.Parent -eq $info.ProcId) { break }
    $cur = $info.Parent
  }
  Write-Host ("=== Port {0} diagnostics ===" -f $Port) -ForegroundColor Cyan
  foreach ($n in $chain) { " PID={0}  Name={1}" -f $n.ProcId, $n.Name }
  $root = $chain[-1]
  "Root PID: {0}" -f $root.ProcId
}

function Stop-Tree {
  param([Parameter(Mandatory)][int]$ProcId)
  # Use taskkill /T to kill whole tree; Stop-Process doesn’t kill children.
  $null = & taskkill /PID $ProcId /T /F 2>$null
}

function Port-Nuke {
  param(
    [Parameter(Mandatory)][int]$Port,
    [int]$MaxAttempts = 6
  )
  for ($i=1; $i -le $MaxAttempts; $i++) {
    $procs = Get-PortListeners -Port $Port
    if (-not $procs) {
      Write-Host ("Port {0} is free." -f $Port) -ForegroundColor Green
      return
    }
    Write-Host ("Attempt {0}/{1}: terminating listeners for port {2} ..." -f $i,$MaxAttempts,$Port) -ForegroundColor Yellow
    foreach ($procId in $procs) {
      Stop-Tree -ProcId $procId
    }
    Start-Sleep -Seconds 1
  }
  Write-Host ("Gave up after {0} attempts. Something keeps respawning on port {1}." -f $MaxAttempts,$Port) -ForegroundColor Red
  Write-Host "Tip: if it's uvicorn with --reload, stop the *reloader* parent window/process, then try again." -ForegroundColor Yellow
}

function Kill-UvicornByPort {
  param([Parameter(Mandatory)][int]$Port)
  $procs = Get-PortListeners -Port $Port
  if (-not $procs) { Write-Host ("Port {0} already free." -f $Port) -ForegroundColor Green; return }
  foreach ($procId in $procs) {
    $info = Get-ProcInfo -ProcId $procId
    if ($info.CommandLine -match 'uvicorn') {
      Stop-Tree -ProcId $procId
    } else {
      Stop-Tree -ProcId $procId
    }
  }
  Start-Sleep 1
  Show-Port -Port $Port
}
