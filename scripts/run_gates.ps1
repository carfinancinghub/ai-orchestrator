# scripts/run_gates.ps1  (PS 5.1 and 7.x compatible)
param(
  [string]$Frontend="C:\Backup_Projects\CFH\frontend",
  [string]$OutDir="C:\c\ai-orchestrator\reports",
  [string]$RunId = $(Get-Date -Format "yyyyMMdd_HHmmss"),
  [int]$BuildTimeoutSec = 900,
  [int]$TestTimeoutSec  = 900,
  [int]$LintTimeoutSec  = 600
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$out = Join-Path $OutDir ("gates_{0}.json" -f $RunId)

function Resolve-NpmCmd {
  $cmd = $null
  try { $cmd = Get-Command npm.cmd -ErrorAction SilentlyContinue } catch {}
  if ($cmd -and $cmd.Source) { return '"' + $cmd.Source + '"' }
  return "npm"
}

function Run-Cmd {
  param([string]$CmdLine, [string]$WorkDir, [int]$TimeoutSec = 600)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $env:ComSpec
  $psi.Arguments = "/c " + $CmdLine
  $psi.WorkingDirectory = $WorkDir
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $completed = $p.WaitForExit($TimeoutSec * 1000)
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  if (-not $completed) {
    try { Stop-Process -Id $p.Id -Force } catch {}
    return [pscustomobject]@{
      ExitCode = 124
      TimedOut = $true
      StdOut   = $stdout
      StdErr   = $stderr
      Cmd      = $CmdLine
      Duration = $TimeoutSec
    }
  }
  [pscustomobject]@{
    ExitCode = $p.ExitCode
    TimedOut = $false
    StdOut   = $stdout
    StdErr   = $stderr
    Cmd      = $CmdLine
  }
}

function First-ErrorLine([string]$txt){
  ($txt -split "`r?`n") | Where-Object {
    $_ -match 'error|fail|failed|TypeError|ReferenceError|TS\d{3,}'
  } | Select-Object -First 1
}

if (-not (Test-Path $Frontend)) { throw "Frontend path not found: $Frontend" }
$npm = Resolve-NpmCmd

# Quick sanity for node/npm
$nodeOk = (Get-Command node -ErrorAction SilentlyContinue)
if (-not $nodeOk) { Write-Warning "node not found on PATH"; }

$env:CI = "1"  # ensure non-interactive test mode

$build = Run-Cmd "$npm run --silent build" $Frontend -TimeoutSec $BuildTimeoutSec
$test  = Run-Cmd "$npm test --silent -- --reporter=default" $Frontend -TimeoutSec $TestTimeoutSec
$lint  = Run-Cmd "$npm run --silent lint" $Frontend -TimeoutSec $LintTimeoutSec

$summary = [ordered]@{
  run_id = $RunId
  meta   = @{ buildCmd=$build.Cmd; testCmd=$test.Cmd; lintCmd=$lint.Cmd }
  build  = @{ exitCode=$build.ExitCode; timedOut=$build.TimedOut; firstError=(First-ErrorLine ($build.StdErr + "`n" + $build.StdOut)) }
  test   = @{ exitCode=$test.ExitCode;  timedOut=$test.TimedOut;  firstError=(First-ErrorLine ($test.StdErr  + "`n" + $test.StdOut)) }
  lint   = @{ exitCode=$lint.ExitCode;  timedOut=$lint.TimedOut;  firstError=(First-ErrorLine ($lint.StdErr  + "`n" + $lint.StdOut)) }
}

$summary | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 $out
Write-Host "Gates written to $out"
