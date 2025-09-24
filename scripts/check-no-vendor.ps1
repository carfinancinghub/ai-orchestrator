# scripts/check-no-vendor.ps1
# Fail CI if vendored/artifact paths are tracked by Git.
# Usage (CI/local): pwsh -File scripts/check-no-vendor.ps1

$ErrorActionPreference = "Stop"
# Normalize git ls-files output to forward slashes
$tracked = (git ls-files) | ForEach-Object { $_ -replace '\\','/' }

$patterns = @(
  '^node_modules/',
  '^\.venv/',
  '^venv/',
  '^artifacts/',
  '^reports/[^/]*_workspace_collect/',
  '^reports/debug/',
  '^dist/',
  '^build/',
  '^coverage/'
)

$bad = @()
foreach ($p in $tracked) {
  foreach ($rx in $patterns) {
    if ($p -match $rx) { $bad += $p; break }
  }
}

if ($bad.Count -gt 0) {
  Write-Error ("Found vendored/artifact files tracked:`n{0}" -f ($bad | Sort-Object -Unique | Out-String))
  exit 1
} else {
  Write-Host "No vendored/artifact files tracked ✅"
}
