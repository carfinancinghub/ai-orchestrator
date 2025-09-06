# scripts/run_gates.ps1  (PowerShell 5.1 compatible)
param(
  [string]$Frontend="C:\Backup_Projects\CFH\frontend",
  [string]$OutDir="C:\c\ai-orchestrator\reports",
  [string]$RunId = $(Get-Date -Format "yyyyMMdd_HHmmss")
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
  param([string]$CmdLine, [string]$WorkDir)
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $env:ComSpec
  $psi.Arguments = "/c " + $CmdLine
  $psi.WorkingDirectory = $WorkDir
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError  = $true
  $psi.UseShellExecute = $false
  $p = [System.Diagnostics.Process]::Start($psi)
  $stdout = $p.StandardOutput.ReadToEnd()
  $stderr = $p.StandardError.ReadToEnd()
  $p.WaitForExit()
  [pscustomobject]@{ ExitCode=$p.ExitCode; StdOut=$stdout; StdErr=$stderr; Cmd=$CmdLine }
}

function First-ErrorLine([string]$txt){
  ($txt -split "`r?`n") | Where-Object {
    $_ -match 'error|fail|failed|TypeError|ReferenceError|TS\d{3,}'
  } | Select-Object -First 1
}

if (-not (Test-Path $Frontend)) { throw "Frontend path not found: $Frontend" }
$npm = Resolve-NpmCmd

$build = Run-Cmd "$npm run --silent build" $Frontend
$test  = Run-Cmd "$npm test --silent -- --reporter=default" $Frontend
$lint  = Run-Cmd "$npm run --silent lint" $Frontend

$summary = [ordered]@{
  run_id = $RunId
  meta   = @{ buildCmd=$build.Cmd; testCmd=$test.Cmd; lintCmd=$lint.Cmd }
  build  = @{ exitCode=$build.ExitCode; firstError=(First-ErrorLine ($build.StdErr + "`n" + $build.StdOut)) }
  test   = @{ exitCode=$test.ExitCode;  firstError=(First-ErrorLine ($test.StdErr  + "`n" + $test.StdOut)) }
  lint   = @{ exitCode=$lint.ExitCode;  firstError=(First-ErrorLine ($lint.StdErr  + "`n" + $lint.StdOut)) }
}

$summary | ConvertTo-Json -Depth 6 | Out-File -Encoding utf8 $out
Write-Host "Gates written to $out"
