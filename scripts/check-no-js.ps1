# scripts/check-no-js.ps1
# Purpose: Block stray .js/.jsx (with smart exceptions) and lightly lint workflow YAML.
# Combines your existing patterns (git-based, fast) with robust array handling + YAML checks.

param()
$ErrorActionPreference = "Stop"

# --- Environment noise off (keeps logs tidy) ---
$env:GIT_TRACE = "0"
$env:GIT_CURL_VERBOSE = "0"

# --- Resolve repo root (fallback to CWD) ---
try {
  $repo = (git rev-parse --show-toplevel).Trim()
} catch {
  $repo = (Get-Location).Path
}

# --- Patterns (kept from your script, extended) ---
# Ignore common build/vendor/test/noise paths
$noisy      = '(\\|/)(node_modules|dist|build|\.next|vendor|coverage|\.git|out|\.turbo|\.cache|venv|\.venv|__pycache__|\.pytest_cache|\.mypy_cache|artifacts\\zip_stage|reports\\debug)(\\|/)'
# Allow tests/mocks & *.test|spec.js(x)
$tests      = '(?i)(^|[\\/])(tests?|__tests__|mocks?|__mocks__)[\\/]|(\.test|\.spec)\.(js|jsx)$'
# Allow common JS config files (at any path)
$allowJsCfg = '(?i)^(eslint|jest|vitest|webpack|vite|rollup|babel|tailwind|postcss|commitlint)\.config\.js$'

# --- Collect tracked JS/JSX via git (fast) ---
$files = @()
$files += $(git -C $repo ls-files *.js  2>$null)
$files += $(git -C $repo ls-files *.jsx 2>$null)

# Normalize to array of non-empty strings
$files = @($files | Where-Object { $_ }) 

# --- Filter out allowed/noisy/test files ---
$bad = @(
  $files | Where-Object {
    # Keep the raw path and a leaf for cfg-match
    $p = $_
    $leaf = Split-Path $p -Leaf
    # Not in noisy dirs, not tests, not allowed cfg
    ($p -notmatch $noisy) -and
    ($p -notmatch $tests) -and
    ($leaf -notmatch $allowJsCfg)
  }
)

if ($bad.Count -gt 0) {
  Write-Host "❌ JS/JSX files blocked:" -ForegroundColor Red
  $bad | ForEach-Object { Write-Host " - $_" }
  throw "pre-commit: validation failed."
} else {
  Write-Host "JS/JSX gate ✅"
}

# --- Optional: YAML validation for Actions workflows (soft fail → only fail on parse error) ---
$wfDir = Join-Path $repo ".github\workflows"
if (Test-Path $wfDir) {
  $yamls = Get-ChildItem $wfDir -Filter *.yml -File -ErrorAction SilentlyContinue
  foreach ($y in $yamls) {
    Write-Host "Validating $($y.FullName)"
    try {
      if (Get-Module -ListAvailable -Name powershell-yaml) {
        $raw = Get-Content $y.FullName -Raw
        # Throws on invalid YAML
        $null = ConvertFrom-Yaml -Yaml $raw
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
