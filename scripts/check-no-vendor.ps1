# scripts/check-no-vendor.ps1
$ErrorActionPreference = 'Stop'

# Directories we disallow in this repo
$blockedDirs = @('node_modules', 'vendor')

# Files we disallow (big zips/tars sneaking in)
$blockedGlobs = @('*.zip','*.tar','*.tar.gz','*.tgz')

$foundDirs  = @()
$foundFiles = @()

foreach ($d in $blockedDirs) {
  $hits = Get-ChildItem -Recurse -Force -Directory -ErrorAction SilentlyContinue `
          | Where-Object { $_.Name -ieq $d }
  if ($hits) { $foundDirs += $hits.FullName }
}

foreach ($g in $blockedGlobs) {
  $hits = Get-ChildItem -Recurse -Force -File -Filter $g -ErrorAction SilentlyContinue
  if ($hits) { $foundFiles += $hits.FullName }
}

if ($foundDirs.Count -or $foundFiles.Count) {
  Write-Host "❌ vendor/node_modules or blocked archives detected:"
  foreach ($p in ($foundDirs + $foundFiles)) { Write-Host " - $p" }
  exit 1
} else {
  Write-Host "Vendor/node_modules guard ✅"
  exit 0
}
