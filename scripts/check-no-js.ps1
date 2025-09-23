# scripts/check-no-js.ps1
# Purpose: Block stray .js/.jsx in source, but:
#  - ignore vendor/build/artifact folders
#  - only scan STAGED files (so untracked workspace noise doesn't block commits)
#  - lightly validate workflow YAML

param()
$ErrorActionPreference = "Stop"

# --- Quiet noisy env vars ---
$env:GIT_TRACE = "0"
$env:GIT_CURL_VERBOSE = "0"

# --- Repo root ---
try {
  $repo = (git rev-parse --show-toplevel).Trim()
} catch {
  $repo = (Get-Location).Path
}

# --- Excluded path prefixes (unix-style) ---
$excludePatterns = @(
  '^node_modules/',
  '^dist/',
  '^build/',
  '^\.next/',
  '^vendor/',
  '^coverage/',
  '^\.git/',
  '^out/',
  '^\.turbo/',
  '^\.cache/',
  '^venv/',
  '^\.venv/',
  '^__pycache__/',
  '^\.pytest_cache/',
  '^\.mypy_cache/',
  '^artifacts/',                       # <-- your orchestrator outputs
  '^reports/[^/]*_workspace_collect/', # <-- snapshot workspace bundles
  '^reports/debug/'                    # <-- debug reports
)

function Is-ExcludedPath($p) {
  $u = ($p -replace '\\','/')
  foreach ($rx in $excludePatterns) { if ($u -match $rx) { return $true } }
  return $false
}

# --- Allow tests & common JS configs ---
$allowTestRx   = '(?i)(^|[\\/])(tests?|__tests__|mocks?|__mocks__)[\\/]|(\.test|\.spec)\.(js|jsx)$'
$allowCfgNames = @(
  'eslint.config.js','jest.config.js','vitest.config.js','webpack.config.js','vite.config.js',
  'rollup.config.js','babel.config.js','tailwind.config.js','postcss.config.js','commitlint.config.js'
)

# --- Only consider STAGED files (Added/Changed) to keep hook focused ---
$staged = @( & git -C $repo diff --cached --name-only --diff-filter=ACM -- '*.js' '*.jsx' 2>$null )
$staged = $staged | Where-Object { $_ }  # non-empty

# If nothing staged, we still print the gate status for clarity
if (-not $staged -or $staged.Count -eq 0) {
  Write-Host "JS/JSX gate ✅ (no staged JS/JSX)"
} else {
  $bad = @()

  foreach ($p in $staged) {
    if (Is-ExcludedPath $p) { continue }

    $leaf = Split-Path $p -Leaf

    # allowed config files anywhere
    if ($allowCfgNames -contains $leaf) { continue }

    # allowed tests/specs
    if ($p -match $allowTestRx) { continue }

    # If it got here, it's a disallowed JS/JSX staged for commit
    $bad += $p
  }

  if ($bad.Count -gt 0) {
    Write-Host "❌ JS/JSX files blocked (staged):" -ForegroundColor Red
    $bad | ForEach-Object { Write-Host " - $_" }
    throw "pre-commit: validation failed."
  } else {
    Write-Host "JS/JSX gate ✅"
  }
}

# --- Optional: validate workflow YAML (soft; fails only on parse error) ---
$wfDir = Join-Path $repo ".github\workflows"
if (Test-Path $wfDir) {
  $yamls = Get-ChildItem $wfDir -Filter *.yml -File -ErrorAction SilentlyContinue
  foreach ($y in $yamls) {
    Write-Host "Validating $($y.FullName)"
    try {
      if (Get-Module -ListAvailable -Name powershell-yaml) {
        $raw = Get-Content $y.FullName -Raw
        $null = ConvertFrom-Yaml -Yaml $raw  # throws on invalid YAML
      } else {
        Write-Warning "ConvertFrom-Yaml not available; skipping strict parse for $($y.FullName)"
      }
    } catch {
      Write-Error "YAML parse failed for $($y.Name): $($_.Exception.Message)"
      throw "pre-commit: validation failed."
    }
  }
}

Write-Host "pre-commit: all checks passed."