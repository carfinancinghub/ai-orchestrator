$ErrorActionPreference = "Stop"
$env:GIT_TRACE = "0"
$env:GIT_CURL_VERBOSE = "0"

$noisy      = '(\\|/)(node_modules|dist|build|\.next|vendor|coverage|\.git|out|\.turbo|\.cache|venv)(\\|/)'
$tests      = '(?i)(^|[\\/])(tests?|__tests__|mocks?|__mocks__)[\\/]|(\.test|\.spec)\.(js|jsx)$'
$allowJsCfg = '^(eslint|jest|vitest|webpack|vite|rollup|babel|tailwind|postcss|commitlint)\.config\.js$'

$files = @()
$files += $(git ls-files *.js  2>$null)
$files += $(git ls-files *.jsx 2>$null)

$bad = $files | Where-Object { $_ -and $_ -notmatch $noisy -and $_ -notmatch $tests -and (Split-Path $_ -Leaf) -notmatch $allowJsCfg }

if ($bad -and $bad.Count) {
  Write-Host "❌ JS/JSX files blocked:`n$($bad -join "`n")"
  exit 1
} else {
  Write-Host "JS/JSX gate ✅"
  exit 0
}
