param()

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Fail($msg){ Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }
function Warn($msg){ Write-Host "WARN:  $msg" -ForegroundColor Yellow }

# Repo root
$repo = (& git rev-parse --show-toplevel) 2>$null
if (-not $repo) { Fail "Cannot locate git repo root." }
Set-Location $repo

# 1) Run your existing JS check if present
$checkNoJs = Join-Path $repo 'scripts\check-no-js.ps1'
if (Test-Path $checkNoJs) {
  Write-Host "Running scripts/check-no-js.ps1 ..."
  & $checkNoJs
  if ($LASTEXITCODE -ne 0) { Fail "check-no-js.ps1 failed." }
} else {
  Write-Host "SKIP scripts/check-no-js.ps1 (not found)"
}

# 2) Validate workflow YAML guards
$fg = Join-Path $repo '.github\workflows\frontend-gates.yml'
$tg = Join-Path $repo '.github\workflows\gates.yml'
$errors = @()

function Test-YamlParse($path){
  try {
    if (Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue) {
      $null = (Get-Content $path -Raw | ConvertFrom-Yaml)
    } else {
      Warn "ConvertFrom-Yaml not available; skipping strict parse for $path"
    }
    return $true
  } catch {
    $errors += "YAML parse failed: $path -> $($_.Exception.Message)"
    return $false
  }
}

function Assert-Contains($path, [string]$needle, [string]$desc){
  $raw = Get-Content $path -Raw
  if ($raw -notmatch [regex]::Escape($needle)) {
    $errors += "$desc missing in $path (expected to contain: $needle)"
  }
}

if (Test-Path $fg) {
  Write-Host "Validating $((Resolve-Path $fg).Path)"
  Test-YamlParse $fg | Out-Null
  Assert-Contains $fg "hashFiles('frontend/package.json')" "frontend guard"
  Assert-Contains $fg "actions/checkout@v4"              "checkout step"
  Assert-Contains $fg "actions/setup-node@v4"            "node setup step"
  Assert-Contains $fg "npm ci"                           "npm ci step"
} else {
  Write-Host "SKIP: $fg (not present)"
}

if (Test-Path $tg) {
  Write-Host "Validating $((Resolve-Path $tg).Path)"
  Test-YamlParse $tg | Out-Null
  Assert-Contains $tg "hashFiles('artifacts/generated/**')" "TS gates guard"
  Assert-Contains $tg "TS Migration Gates"                  "workflow name"
} else {
  Write-Host "SKIP: $tg (not present)"
}

if ($errors.Count -gt 0) {
  $errors | ForEach-Object { Write-Host "ERROR: $_" -ForegroundColor Red }
  exit 1
}

Write-Host "pre-commit: all checks passed." -ForegroundColor Green
exit 0
