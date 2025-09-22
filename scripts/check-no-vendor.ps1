# scripts/check-no-vendor.ps1
# Blocks committed vendor directories like node_modules/ and vendor/
# Scans only tracked files to avoid noise from local caches.

$ErrorActionPreference = "Stop"

# List all tracked files in the repo
$tracked = & git ls-files 2>$null

# Nothing to check?
if (-not $tracked) {
  Write-Host "vendor guard ✅ (no tracked files)"
  exit 0
}

# Pattern: a path segment named node_modules or vendor
$bad = $tracked | Where-Object {
  $_ -match '(^|[\\/])(node_modules|vendor)([\\/]|$)'
}

# Allowlist: if you ever need to permit specific subpaths, put them here
$allowlist = @(
  # Example: '^tools[\\/]vendor[\\/]some-allowed-lib[\\/]'
)

if ($bad) {
  # Apply allowlist
  $disallowed = @()
  foreach ($p in $bad) {
    $allowed = $false
    foreach ($pat in $allowlist) {
      if ($p -match $pat) { $allowed = $true; break }
    }
    if (-not $allowed) { $disallowed += $p }
  }

  if ($disallowed.Count -gt 0) {
    Write-Host "❌ vendor guard: disallowed paths detected:`n - " + ($disallowed -join "`n - ")
    throw "vendor guard failed."
  }
}

Write-Host "vendor guard ✅"
exit 0
