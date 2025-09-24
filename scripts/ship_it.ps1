param(
  [string]$FrontPath = $env:FRONTEND_PATH
)

$ErrorActionPreference = "Stop"

function Require-Front([string]$Path) {
  if (-not $Path -or -not (Test-Path $Path)) {
    throw "Frontend path not found. Provide -FrontPath or set `$env:FRONTEND_PATH` or create .orchestrator\frontend_path.txt"
  }
}

function Get-FrontStamp([string]$Path) {
  try {
    $cur = git -C $Path branch --show-current 2>$null
    if ($cur -and $cur -match '^ts-migration/(.+)$') { return $Matches[1] }
  } catch {}
  try {
    $heads = git -C $Path ls-remote --heads origin "ts-migration/*" 2>$null |
      ForEach-Object { ($_ -split "`t")[1] -replace '^refs/heads/','' } | Sort-Object
    if ($heads.Count) { return ($heads[-1] -split '/',2)[1] }
  } catch {}
  return $null
}

# NEW: resolve FrontPath from config if not provided/env
if (-not $FrontPath -or -not (Test-Path $FrontPath)) {
  $cfg = Join-Path $PSScriptRoot '..\.orchestrator\frontend_path.txt'
  if (Test-Path $cfg) {
    $FrontPath = (Get-Content $cfg -Raw).Trim()
  }
}

Require-Front $FrontPath

Write-Host "=== 1) Publish (branches + summary) ==="
pwsh -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\publish_all.ps1"

$stamp = Get-FrontStamp $FrontPath
if (-not $stamp) { throw "Could not determine ts-migration/<stamp> after publish." }
$env:stamp = $stamp
$env:FRONTEND_PATH = $FrontPath
Write-Host "Using stamp: $env:stamp"

Write-Host "=== 2) Analyze + comment PR ==="
pwsh -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\analyze_and_comment.ps1" -FrontPath $FrontPath -Stamp $env:stamp

Write-Host "=== 3) Synthesize + commit stubs (if any) ==="
pwsh -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\synthesize_and_commit.ps1" -FrontPath $FrontPath -Stamp $env:stamp

Write-Host "✅ Done."
